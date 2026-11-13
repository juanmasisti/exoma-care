from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities.logistics import TIMEZONE, AppointmentStatus, study_code
from app.domain.interfaces.appointment_repository import SlotOrStudyTaken
from app.infrastructure.database.logistics_models import AppointmentModel, ExtractionCenterModel
from app.infrastructure.database.models import Paciente
from app.infrastructure.database.study_models import StudyModel

BOOKED = AppointmentStatus.BOOKED.value


class SQLAlchemyAppointmentRepository:
    def __init__(self, session: Session):
        self.session = session

    def study_status_for_user(self, study_id: int, user_id: int) -> str | None:
        # PROVISORIO (decisión 005, T02): lectura directa de studies y patients hasta que
        # estudios y pacientes ofrezcan "estudio del usuario". Solo lectura.
        return self.session.scalar(
            select(StudyModel.status).join(Paciente, Paciente.id == StudyModel.patient_id)
            .where(StudyModel.id == study_id, Paciente.usuario_id == user_id)
        )

    def studies_without_booking_for_user(self, user_id: int) -> list[dict]:
        # PROVISORIO (decisión 005, T02): lectura directa hasta que estudios ofrezca la lista
        # de estudios del paciente. Solo lectura.
        has_booking = select(AppointmentModel.id).where(
            AppointmentModel.study_id == StudyModel.id, AppointmentModel.status == BOOKED).exists()
        rows = self.session.execute(
            select(StudyModel.id, StudyModel.status).join(Paciente, Paciente.id == StudyModel.patient_id)
            .where(Paciente.usuario_id == user_id, ~has_booking).order_by(StudyModel.id)
        )
        return [{"id": id_, "status": status} for id_, status in rows]

    def study_has_booked(self, study_id: int) -> bool:
        return self.session.scalar(select(func.count()).select_from(AppointmentModel).where(
            AppointmentModel.study_id == study_id, AppointmentModel.status == BOOKED)) > 0

    def add(self, study_id: int, center_id: int, starts_at: datetime, study_status_before: str) -> int:
        appointment = AppointmentModel(study_id=study_id, center_id=center_id, starts_at=starts_at,
                                       status=BOOKED, study_status_before=study_status_before)
        self.session.add(appointment)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise SlotOrStudyTaken() from None
        return appointment.id

    def _select(self):
        return (select(AppointmentModel, ExtractionCenterModel, Paciente)
                .join(ExtractionCenterModel, ExtractionCenterModel.id == AppointmentModel.center_id)
                .join(StudyModel, StudyModel.id == AppointmentModel.study_id)
                .join(Paciente, Paciente.id == StudyModel.patient_id))

    @staticmethod
    def _record(row) -> dict:
        appointment, center, patient = row
        return {"id": appointment.id, "study_id": appointment.study_id, "study_code": study_code(appointment.study_id),
                "starts_at": appointment.starts_at.astimezone(TIMEZONE), "status": appointment.status,
                "study_status_before": appointment.study_status_before,
                "patient_id": patient.id, "patient_user_id": patient.usuario_id,
                # Para los documentos del turno; los endpoints de turnos no lo exponen.
                "patient": {"first_name": patient.nombre, "last_name": patient.apellido, "dni": patient.dni},
                "center": {"id": center.id, "name": center.name, "address": center.address,
                           "city": center.city, "phone": center.phone}}

    def get(self, appointment_id: int) -> dict | None:
        row = self.session.execute(self._select().where(AppointmentModel.id == appointment_id)).first()
        return self._record(row) if row is not None else None

    def booked_for_study(self, study_id: int) -> dict | None:
        row = self.session.execute(self._select().where(
            AppointmentModel.study_id == study_id, AppointmentModel.status == BOOKED)).first()
        return self._record(row) if row is not None else None

    def booked_for_user(self, user_id: int) -> list[dict]:
        rows = self.session.execute(self._select().where(
            Paciente.usuario_id == user_id, AppointmentModel.status == BOOKED).order_by(AppointmentModel.starts_at))
        return [self._record(row) for row in rows]

    def finish(self, appointment_id: int, status: str, cancelled_at: datetime | None = None) -> bool:
        # Condicional: si otro pedido ya lo cerró, no se pisa.
        result = self.session.execute(
            update(AppointmentModel)
            .where(AppointmentModel.id == appointment_id, AppointmentModel.status == BOOKED)
            .values(status=status, cancelled_at=cancelled_at)
        )
        return result.rowcount == 1

    def count_absences(self, patient_id: int) -> int:
        return self.session.scalar(
            select(func.count()).select_from(AppointmentModel)
            .join(StudyModel, StudyModel.id == AppointmentModel.study_id)
            .where(StudyModel.patient_id == patient_id, AppointmentModel.status == AppointmentStatus.ABSENT.value)
        )

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
