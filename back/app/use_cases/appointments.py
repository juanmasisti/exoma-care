from datetime import datetime

from app.domain.entities.logistics import TIMEZONE, AppointmentStatus, can_change_appointment, is_valid_slot
from app.domain.interfaces.appointment_repository import AppointmentRepository, SlotOrStudyTaken
from app.domain.interfaces.extraction_center_repository import ExtractionCenterRepository
from app.use_cases.studies import StudyService

STUDY_NOT_FOUND = "El estudio no existe o no es tuyo."
APPOINTMENT_NOT_FOUND = "El turno no existe."


class NotFound(Exception):
    pass


class InvalidSlot(ValueError):
    pass


class AppointmentConflict(Exception):
    pass


class AppointmentService:
    def __init__(self, appointments: AppointmentRepository, centers: ExtractionCenterRepository,
                 studies: StudyService):
        self.appointments = appointments
        self.centers = centers
        self.studies = studies

    def reservar(self, user_id: int, study_id: int, center_id: int, starts_at: datetime, now: datetime) -> dict:
        study_status = self.appointments.study_status_for_user(study_id, user_id)
        if study_status is None:
            raise NotFound(STUDY_NOT_FOUND)
        if not self.studies.estudio_habilitado(study_id):
            raise AppointmentConflict("El estudio no está habilitado para sacar turno: tiene que estar "
                                      "pagado o autorizado y sin otro turno vigente.")
        if self.centers.get_active_center(center_id) is None:
            raise NotFound("El centro de extracción no existe o no está activo.")
        day = starts_at.astimezone(TIMEZONE).date()
        holidays = {day} if self.centers.holiday(day) is not None else set()
        if not is_valid_slot(starts_at, holidays):
            raise InvalidSlot("El horario no es un turno válido: de lunes a viernes no feriados, "
                              "de 9 a 17:45, cada 15 minutos.")
        if starts_at <= now:
            raise InvalidSlot("El horario elegido ya pasó.")
        try:
            appointment_id = self.appointments.add(study_id, center_id, starts_at, study_status)
        except SlotOrStudyTaken:
            if self.appointments.study_has_booked(study_id):
                raise AppointmentConflict("El estudio ya tiene un turno vigente.") from None
            raise AppointmentConflict("El horario ya está reservado en este centro.") from None
        self._commit_with(lambda: self.studies.cambiar_estado_estudio(study_id, "turno_sacado"))
        return self.appointments.get(appointment_id)

    def cancelar(self, user_id: int, appointment_id: int, now: datetime) -> None:
        appointment = self.appointments.get(appointment_id)
        if appointment is None or appointment["patient_user_id"] != user_id:
            raise NotFound(APPOINTMENT_NOT_FOUND)
        not_booked = "Solo se puede cancelar un turno reservado."
        if not can_change_appointment(AppointmentStatus(appointment["status"]), AppointmentStatus.CANCELLED):
            raise AppointmentConflict(not_booked)
        # A confirmar con el profesor: así no se esquiva la inasistencia cancelando después del turno.
        if appointment["starts_at"] <= now:
            raise AppointmentConflict("No se puede cancelar un turno que ya empezó.")
        # Si estudios ya avanzó el estado, restaurar study_status_before lo haría retroceder.
        if self.appointments.study_status_for_user(appointment["study_id"], user_id) != "turno_sacado":
            raise AppointmentConflict("El turno ya no se puede cancelar: el estudio pasó a otra etapa.")
        self._close(appointment, AppointmentStatus.CANCELLED, not_booked, cancelled_at=now)
        self._commit_with(lambda: self.studies.cambiar_estado_estudio(appointment["study_id"],
                                                                      appointment["study_status_before"]))

    def turno_del_estudio(self, user_id: int, study_id: int) -> dict:
        if self.appointments.study_status_for_user(study_id, user_id) is None:
            raise NotFound(STUDY_NOT_FOUND)
        appointment = self.appointments.booked_for_study(study_id)
        if appointment is None:
            raise NotFound("El estudio no tiene un turno vigente.")
        return appointment

    def registrar_asistencia(self, appointment_id: int, attended: bool) -> dict:
        appointment = self.appointments.get(appointment_id)
        if appointment is None:
            raise NotFound(APPOINTMENT_NOT_FOUND)
        status = AppointmentStatus.ATTENDED if attended else AppointmentStatus.ABSENT
        self._close(appointment, status, "Solo se registra la asistencia de un turno reservado.")
        self.appointments.commit()
        # ABIERTO (decisión 7 del dominio): sanción por inasistencias; por ahora solo el contador.
        return {"id": appointment_id, "status": status.value,
                "patient_absences": self.appointments.count_absences(appointment["patient_id"])}

    def _close(self, appointment: dict, status: AppointmentStatus, conflict: str, cancelled_at=None) -> None:
        """Cierra el turno en la sesión, sin confirmar. `finish` vuelve a mirar el estado por si otro pedido ganó."""
        if (not can_change_appointment(AppointmentStatus(appointment["status"]), status)
                or not self.appointments.finish(appointment["id"], status.value, cancelled_at)):
            self.appointments.rollback()
            raise AppointmentConflict(conflict)

    def _commit_with(self, change) -> None:
        # El turno y el cambio de estado del estudio se confirman juntos o no se confirma nada.
        try:
            change()
            self.appointments.commit()
        except Exception:
            self.appointments.rollback()
            raise
