from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.domain.entities.logistics import TIMEZONE, AppointmentStatus, SampleStatus
from app.domain.interfaces.sample_repository import CurrentSampleExists, NoticeAlreadyReceived
from app.infrastructure.database.logistics_models import (
    AppointmentModel, ExtractionNoticeModel, SampleEventModel, SampleModel,
)
from app.infrastructure.database.models import Paciente
from app.infrastructure.database.study_models import StudyModel


class SQLAlchemySampleRepository:
    def __init__(self, session: Session):
        self.session = session

    def study_status(self, study_id: int) -> str | None:
        # PROVISORIO (decisión 011): lectura directa de studies hasta que estudios la ofrezca. Solo lectura.
        return self.session.scalar(select(StudyModel.status).where(StudyModel.id == study_id))

    def notice_result(self, external_id: str) -> dict | None:
        row = self.session.execute(
            select(ExtractionNoticeModel.payload, SampleModel.id, SampleModel.volume_ml)
            .join(SampleModel, SampleModel.extraction_notice_id == ExtractionNoticeModel.id)
            .where(ExtractionNoticeModel.external_id == external_id)
        ).first()
        if row is None:
            return None
        payload, sample_id, volume_ml = row
        return {"payload": payload, "sample_id": sample_id, "volume_ml": volume_ml}

    def add_notice(self, external_id: str, payload: dict, received_at: datetime) -> int:
        notice = ExtractionNoticeModel(external_id=external_id, payload=payload, received_at=received_at)
        self.session.add(notice)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise NoticeAlreadyReceived() from None
        return notice.id

    def appointment_for_notice(self, study_id: int) -> dict | None:
        # Primero el turno reservado (en remuestreo el nuevo puede ser anterior al viejo ya asistido);
        # si no hay, uno asistido que todavía no tenga muestra. Cancelados y ausentes no cuentan.
        without_sample = ~select(SampleModel.id).where(SampleModel.appointment_id == AppointmentModel.id).exists()
        row = (self._last_appointment(study_id, AppointmentStatus.BOOKED)
               or self._last_appointment(study_id, AppointmentStatus.ATTENDED, without_sample))
        return {"id": row.id, "status": row.status} if row is not None else None

    def _last_appointment(self, study_id: int, status: AppointmentStatus, *where):
        return self.session.execute(
            select(AppointmentModel.id, AppointmentModel.status)
            .where(AppointmentModel.study_id == study_id, AppointmentModel.status == status.value, *where)
            .order_by(AppointmentModel.starts_at.desc()).limit(1)
        ).first()

    def add_sample(self, study_id: int, appointment_id: int, notice_id: int, volume_ml: Decimal,
                   status: str, is_current: bool) -> int:
        sample = SampleModel(study_id=study_id, appointment_id=appointment_id, extraction_notice_id=notice_id,
                             volume_ml=volume_ml, status=status, is_current=is_current)
        self.session.add(sample)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise CurrentSampleExists() from None
        return sample.id

    def add_event(self, sample_id: int, from_status: str | None, to_status: str, at: datetime,
                  actor_id: int | None = None, reason: str | None = None) -> None:
        self.session.add(SampleEventModel(sample_id=sample_id, from_status=from_status, to_status=to_status,
                                          at=at, actor_id=actor_id, reason=reason))
        self.session.flush()

    def current_sample(self, study_id: int) -> dict | None:
        sample = self.session.scalar(select(SampleModel).where(SampleModel.study_id == study_id,
                                                                SampleModel.is_current.is_(True)))
        return {"id": sample.id, "status": sample.status} if sample is not None else None

    def discard(self, sample_id: int, from_status: str) -> bool:
        # Condicional: si otro pedido ya la cambió, no se pisa.
        result = self.session.execute(
            update(SampleModel)
            .where(SampleModel.id == sample_id, SampleModel.status == from_status, SampleModel.is_current.is_(True))
            .values(status=SampleStatus.DISCARDED.value, is_current=False)
        )
        return result.rowcount == 1

    def samples_with_events(self, study_id: int) -> list[dict]:
        samples = self.session.scalars(select(SampleModel).where(SampleModel.study_id == study_id)
                                       .order_by(SampleModel.id)).all()
        events = self.session.scalars(
            select(SampleEventModel).where(SampleEventModel.sample_id.in_([sample.id for sample in samples]))
            .order_by(SampleEventModel.at, SampleEventModel.id)
        ).all()
        return [{"id": sample.id, "volume_ml": sample.volume_ml, "status": sample.status,
                 "is_current": sample.is_current,
                 "events": [{"from_status": event.from_status, "to_status": event.to_status,
                             "reason": event.reason, "at": event.at.astimezone(TIMEZONE)}
                            for event in events if event.sample_id == sample.id]}
                for sample in samples]

    def studies_with_samples_for_user(self, user_id: int) -> list[dict]:
        # PROVISORIO (decisión 013): lectura directa de studies y patients, como en turnos, hasta que
        # estudios ofrezca la lista de estudios del paciente. Solo lectura.
        current = aliased(SampleModel)
        has_sample = select(SampleModel.id).where(SampleModel.study_id == StudyModel.id).exists()
        rows = self.session.execute(
            select(StudyModel.id, StudyModel.status, current.status)
            .join(Paciente, Paciente.id == StudyModel.patient_id)
            .outerjoin(current, (current.study_id == StudyModel.id) & current.is_current.is_(True))
            .where(Paciente.usuario_id == user_id, has_sample).order_by(StudyModel.id)
        )
        return [{"id": id_, "status": status, "current_sample_status": sample_status}
                for id_, status, sample_status in rows]

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
