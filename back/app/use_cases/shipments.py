"""Envío del lote al laboratorio de secuenciación: CSV, autorización del Ministerio y retiro de FedEx (EC-18)."""
import csv
import io
import logging
from datetime import datetime
from pathlib import Path

from app.domain.entities.logistics import (
    TIMEZONE, SampleSetStatus, SampleStatus, is_valid_pickup_time, study_code,
)
from app.domain.entities.study import StudyStatus
from app.domain.interfaces.courier import Courier, CourierError, PickupStatus
from app.domain.interfaces.extraction_center_repository import ExtractionCenterRepository
from app.domain.interfaces.health_ministry import HealthMinistry
from app.domain.interfaces.patient_repository import PatientRepository
from app.domain.interfaces.sample_repository import SampleRepository
from app.domain.interfaces.shipment_repository import ShipmentRepository
from app.use_cases.studies import StudyService

logger = logging.getLogger(__name__)

CSV_COLUMNS = ("dni", "apellido", "nombre", "codigo_estudio", "id_muestra")
CLOSED = SampleSetStatus.CLOSED.value
AWAITING_PICKUP = SampleSetStatus.AWAITING_PICKUP.value
IN_TRANSIT = SampleSetStatus.IN_TRANSIT_TO_SEQUENCING_LAB.value


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class InvalidPickup(Exception):
    pass


class ExternalServiceError(Exception):
    """El Ministerio o FedEx fallaron: el lote no cambia."""


class ShipmentService:
    def __init__(self, shipments: ShipmentRepository, patients: PatientRepository, samples: SampleRepository,
                 studies: StudyService, ministry: HealthMinistry, centers: ExtractionCenterRepository,
                 files_dir: Path, lab_address: str):
        self.shipments = shipments
        self.patients = patients
        self.samples = samples
        self.studies = studies
        self.ministry = ministry
        self.centers = centers
        self.files_dir = files_dir
        self.lab_address = lab_address

    def al_cerrar_lote(self, sample_set_id: int, now: datetime) -> None:
        """Enganche del armado de lotes (T05). Sin commit: lo hace quien atiende el pedido."""
        try:
            self._authorize(sample_set_id)
        except (ExternalServiceError, Conflict):
            # El lote queda cerrado sin PDF y se reintenta con `autorizar`; no deshace la llegada.
            logger.exception("No se pudo pedir la autorización del lote %s.", sample_set_id)

    def envio(self, sample_set_id: int) -> dict:
        shipment = self._get(sample_set_id)
        pickup_at = shipment["pickup_at"]
        return {"id": shipment["id"], "status": shipment["status"],
                "has_csv": shipment["csv_path"] is not None,
                "has_authorization": shipment["authorization_pdf_path"] is not None,
                "pickup_at": pickup_at.astimezone(TIMEZONE) if pickup_at else None,
                "courier_pickup_id": shipment["courier_pickup_id"]}

    def archivo(self, sample_set_id: int, column: str) -> Path:
        """`column`: csv_path o authorization_pdf_path."""
        name = self._get(sample_set_id)[column]
        path = self.files_dir / name if name else None
        if path is None or not path.is_file():
            raise NotFound("El lote todavía no tiene ese archivo.")
        return path

    def autorizar(self, sample_set_id: int) -> dict:
        shipment = self._get(sample_set_id)
        if shipment["authorization_pdf_path"] is not None:
            raise Conflict("El lote ya tiene la autorización del Ministerio de Salud.")
        if shipment["status"] != CLOSED:
            raise Conflict("El lote todavía se está armando.")
        self._in_transaction(lambda: self._authorize(sample_set_id))
        return self.envio(sample_set_id)

    def programar_retiro(self, sample_set_id: int, scheduled_at: datetime, now: datetime, courier: Courier) -> dict:
        shipment = self._get(sample_set_id)
        if shipment["status"] != CLOSED:
            raise Conflict("El lote ya tiene un retiro programado." if shipment["courier_pickup_id"]
                           else "El lote todavía se está armando.")
        if shipment["authorization_pdf_path"] is None:
            raise Conflict("Falta la autorización del Ministerio de Salud.")
        if scheduled_at <= now:
            raise InvalidPickup("La fecha del retiro tiene que ser futura.")
        day = scheduled_at.astimezone(TIMEZONE).date()
        holidays = {day} if self.centers.holiday(day) else set()
        if not is_valid_pickup_time(scheduled_at, holidays):
            raise InvalidPickup("FedEx retira en días hábiles, de 9 a 18 h.")
        try:
            pickup_id = courier.programar_retiro(self.lab_address, scheduled_at)
        except CourierError as exc:
            raise ExternalServiceError(str(exc)) from exc

        def schedule():
            # Si otro pedido programó antes, el retiro que se acaba de pedir queda sin usar en FedEx.
            if not self.shipments.schedule_pickup(sample_set_id, pickup_id, scheduled_at):
                raise Conflict("Otro pedido ya programó el retiro del lote.")
        self._in_transaction(schedule)
        return self.envio(sample_set_id)

    def actualizar_estado(self, sample_set_id: int, now: datetime, courier: Courier, actor_id: int | None) -> dict:
        shipment = self._get(sample_set_id)
        if shipment["status"] == IN_TRANSIT:
            return self.envio(sample_set_id)
        if shipment["status"] != AWAITING_PICKUP:
            raise Conflict("El lote no tiene un retiro programado.")
        try:
            status = courier.estado_retiro(shipment["courier_pickup_id"])
        except CourierError as exc:
            raise ExternalServiceError(str(exc)) from exc
        if status == PickupStatus.RETIRADO:
            self._in_transaction(lambda: self._depart(sample_set_id, now, actor_id))
        return self.envio(sample_set_id)

    def _depart(self, sample_set_id: int, now: datetime, actor_id: int | None) -> None:
        # Solo el pedido que mueve el lote mueve muestras y estudios: consultar dos veces no repite nada.
        if not self.shipments.mark_in_transit(sample_set_id):
            return
        items = self.shipments.items(sample_set_id)
        self.samples.change_status([item["sample_id"] for item in items], SampleStatus.IN_SAMPLE_SET.value,
                                   SampleStatus.IN_TRANSIT_TO_SEQUENCING_LAB.value, now, actor_id)
        for item in items:
            self.studies.cambiar_estado_estudio(item["study_id"], StudyStatus.IN_TRANSIT_TO_KOREA)

    def _authorize(self, sample_set_id: int) -> None:
        csv_text = self._csv(sample_set_id)
        try:
            authorization = self.ministry.solicitar_autorizacion(csv_text)
        except Exception as exc:  # servicio externo: cualquier falla deja el lote sin PDF
            raise ExternalServiceError("El Ministerio de Salud no respondió. Reintentá la autorización.") from exc
        csv_name, pdf_name = f"lote-{sample_set_id}.csv", f"lote-{sample_set_id}-autorizacion.pdf"
        try:
            self.files_dir.mkdir(parents=True, exist_ok=True)
            (self.files_dir / csv_name).write_text(csv_text, encoding="utf-8", newline="")
            (self.files_dir / pdf_name).write_bytes(authorization.pdf)
        except OSError as exc:
            raise ExternalServiceError("No se pudo guardar la autorización. Reintentá más tarde.") from exc
        if not self.shipments.save_authorization(sample_set_id, csv_name, pdf_name):
            raise Conflict("Otro pedido ya autorizó el lote.")

    def _csv(self, sample_set_id: int) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(CSV_COLUMNS)
        for item in self.shipments.items(sample_set_id):
            patient = self.patients.get(item["patient_id"], None)
            writer.writerow((patient["dni"], patient["last_name"], patient["first_name"],
                             study_code(item["study_id"]), item["sample_id"]))
        return output.getvalue()

    def _get(self, sample_set_id: int) -> dict:
        shipment = self.shipments.get(sample_set_id)
        if shipment is None:
            raise NotFound("El lote no existe.")
        return shipment

    def _in_transaction(self, change) -> None:
        try:
            change()
            self.shipments.commit()
        except Exception:
            self.shipments.rollback()
            raise
