import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.entities.logistics import (
    MIN_SAMPLE_VOLUME_ML, AppointmentStatus, SampleStatus, can_change_sample, initial_sample_status, study_code,
    study_id_from_code,
)
from app.domain.interfaces.appointment_repository import AppointmentRepository
from app.domain.interfaces.resample_notifier import ResampleNotifier
from app.domain.interfaces.sample_repository import CurrentSampleExists, NoticeAlreadyReceived, SampleRepository
from app.use_cases.studies import StudyService

logger = logging.getLogger(__name__)

READY_FOR_PICKUP = "listo_para_retirar"
REQUIRES_RESAMPLE = "requiere_remuestreo"
# Estado del estudio que deja una muestra recién creada, según el estado con el que nace.
STUDY_STATUS_FOR_NEW_SAMPLE = {SampleStatus.READY_FOR_PICKUP: READY_FOR_PICKUP,
                               SampleStatus.DISCARDED: REQUIRES_RESAMPLE}


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class ExtractionService:
    def __init__(self, samples: SampleRepository, appointments: AppointmentRepository, studies: StudyService,
                 notifier: ResampleNotifier):
        self.samples = samples
        self.appointments = appointments
        self.studies = studies
        self.notifier = notifier

    def registrar_aviso(self, external_id: str, code: str, volume_ml: Decimal, taken_at: datetime,
                        now: datetime) -> tuple[dict, bool]:
        """Devuelve el resultado y si se creó ahora (False: aviso repetido, mismo resultado que la primera vez)."""
        payload = {"study_code": code, "volume_ml": str(volume_ml.quantize(Decimal("0.01"))),
                   "taken_at": taken_at.astimezone(UTC).isoformat()}
        previous = self.samples.notice_result(external_id)
        if previous is not None:
            return self._repeated(external_id, previous, payload), False
        try:
            # En SQLite este INSERT toma el lock de escritura: dos avisos distintos del mismo estudio quedan
            # en fila y el segundo lee lo que confirmó el primero (409). En otro motor haría falta que el
            # cambio de estado del estudio sea condicional (pedírselo a estudios).
            notice_id = self.samples.add_notice(external_id, payload, now)
        except NoticeAlreadyReceived:  # otro pedido con el mismo aviso ganó la carrera
            return self._repeated(external_id, self.samples.notice_result(external_id), payload), False
        try:
            study_id = study_id_from_code(code)
            study_status = self.samples.study_status(study_id) if study_id is not None else None
            if study_status is None:
                raise NotFound("El estudio no existe.")
            if study_status != "turno_sacado":
                raise Conflict("El estudio no está esperando una extracción.")
            appointment_id = self._attended_appointment(study_id)
            status = initial_sample_status(volume_ml)
            try:
                sample_id = self.samples.add_sample(study_id, appointment_id, notice_id, volume_ml, status.value,
                                                    is_current=status is SampleStatus.READY_FOR_PICKUP)
            except CurrentSampleExists:
                raise Conflict("El estudio ya tiene una muestra vigente.") from None
            self.samples.add_event(sample_id, None, status.value, taken_at)
            self.studies.cambiar_estado_estudio(study_id, STUDY_STATUS_FOR_NEW_SAMPLE[status])
            self.samples.commit()
        except Exception:
            self.samples.rollback()
            raise
        if status is SampleStatus.DISCARDED:
            self._notify(study_id, f"Volumen insuficiente: {volume_ml} ml (mínimo {MIN_SAMPLE_VOLUME_ML} ml).")
        return self._result(sample_id, status), True

    def solicitar_remuestreo(self, study_id: int, motivo: str, now: datetime, actor_id: int | None = None) -> None:
        """Para bioinformática (Camila) cuando el ADN es insuficiente. Mismo estudio; no toca pagos."""
        motivo = motivo.strip()
        if not motivo or len(motivo) > 500:
            raise ValueError("El motivo es obligatorio y tiene hasta 500 caracteres.")
        sample = self.samples.current_sample(study_id)
        if sample is None:
            raise NotFound("El estudio no existe o no tiene una muestra vigente.")
        current = SampleStatus(sample["status"])
        if not can_change_sample(current, SampleStatus.DISCARDED):
            raise Conflict(f"No se puede remuestrear una muestra en estado {current.value}.")
        try:
            if not self.samples.discard(sample["id"], current.value):
                raise Conflict("La muestra cambió mientras se pedía el remuestreo.")
            self.samples.add_event(sample["id"], current.value, SampleStatus.DISCARDED.value, now, actor_id, motivo)
            self.studies.cambiar_estado_estudio(study_id, REQUIRES_RESAMPLE)
            self.samples.commit()
        except Exception:
            self.samples.rollback()
            raise
        self._notify(study_id, motivo)

    def seguimiento(self, user_id: int, study_id: int) -> dict:
        status = self.appointments.study_status_for_user(study_id, user_id)
        if status is None:
            raise NotFound("El estudio no existe o no es tuyo.")
        return {"study_id": study_id, "code": study_code(study_id), "status": status,
                "requires_new_extraction": status == REQUIRES_RESAMPLE,
                "samples": self.samples.samples_with_events(study_id)}

    def _attended_appointment(self, study_id: int) -> int:
        """El aviso prueba que el paciente fue: un turno reservado pasa a asistido (decisión 011)."""
        appointment = self.samples.last_appointment(study_id)
        if appointment is None or appointment["status"] == AppointmentStatus.ABSENT.value:
            raise Conflict("El estudio no tiene un turno reservado o asistido para esta extracción.")
        # Condicional, como en turnos: si el paciente cancela a la vez, gana uno solo.
        if (appointment["status"] == AppointmentStatus.BOOKED.value
                and not self.appointments.finish(appointment["id"], AppointmentStatus.ATTENDED.value)):
            raise Conflict("El turno cambió mientras se registraba la extracción.")
        return appointment["id"]

    def _repeated(self, external_id: str, previous: dict, payload: dict) -> dict:
        if previous["payload"] != payload:
            logger.warning("Aviso de extracción %s repetido con otro contenido; se devuelve el resultado original.",
                           external_id)
        return self._result(previous["sample_id"], initial_sample_status(previous["volume_ml"]))

    @staticmethod
    def _result(sample_id: int, status: SampleStatus) -> dict:
        # El resultado de la primera vez: el estado con el que nació la muestra, no el de hoy.
        return {"sample_id": sample_id, "sample_status": status.value,
                "study_status": STUDY_STATUS_FOR_NEW_SAMPLE[status]}

    def _notify(self, study_id: int, motivo: str) -> None:
        # Lo guardado ya está confirmado: un aviso fallido no lo deshace ni hace fallar el pedido.
        try:
            self.notifier.avisar_remuestreo(study_id, motivo)
        except Exception:
            logger.exception("No se pudo avisar el remuestreo del estudio %s.", study_id)
