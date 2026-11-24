from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, insert, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.domain.entities.logistics import SAMPLE_SET_SIZE, SampleSetStatus
from app.domain.interfaces.sample_set_repository import (
    AssemblingSetExists, SampleAlreadyInSet, SetFull, SetNotAssembling, SlotTaken,
)
from app.infrastructure.database.logistics_models import SampleModel, SampleSetItemModel, SampleSetModel
from app.infrastructure.database.models import Paciente
from app.infrastructure.database.study_models import StudyModel, StudyPathologyModel


class SQLAlchemySampleSetRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, sample_set_id: int) -> dict | None:
        sample_set = self.session.get(SampleSetModel, sample_set_id)
        return self._record(sample_set) if sample_set is not None else None

    def list_by_status(self, status: str | None) -> list[dict]:
        count = (select(func.count(SampleSetItemModel.id))
                 .where(SampleSetItemModel.sample_set_id == SampleSetModel.id).scalar_subquery())
        query = select(SampleSetModel, count).order_by(SampleSetModel.id.desc())
        if status is not None:
            query = query.where(SampleSetModel.status == status)
        return [{"id": sample_set.id, "status": sample_set.status, "is_urgent": sample_set.is_urgent,
                 "created_at": sample_set.created_at, "closed_at": sample_set.closed_at, "sample_count": sample_count}
                for sample_set, sample_count in self.session.execute(query)]

    def assembling(self) -> dict | None:
        sample_set = self.session.scalar(select(SampleSetModel)
                                         .where(SampleSetModel.status == SampleSetStatus.ASSEMBLING.value))
        return self._record(sample_set) if sample_set is not None else None

    def open_set(self, is_urgent: bool, now: datetime) -> int:
        sample_set = SampleSetModel(status=SampleSetStatus.ASSEMBLING.value, is_urgent=is_urgent, created_at=now)
        try:
            # Savepoint: el choque deshace solo este lote, no las muestras recibidas del mismo pedido.
            with self.session.begin_nested():
                self.session.add(sample_set)
                self.session.flush()
        except IntegrityError:
            raise AssemblingSetExists() from None
        return sample_set.id

    def add_item(self, sample_set_id: int, sample_id: int, slot: int) -> None:
        if not 1 <= slot <= SAMPLE_SET_SIZE:
            raise SetFull()
        # INSERT condicional: solo entra si el lote sigue armándose al escribir, así un cierre que ganó
        # antes (por ejemplo un Pompe urgente) no deja sumar muestras a un lote cerrado.
        assembling = (select(SampleSetModel.id).where(SampleSetModel.id == sample_set_id,
                                                      SampleSetModel.status == SampleSetStatus.ASSEMBLING.value)
                      .exists())
        row = select(literal(sample_set_id), literal(sample_id), literal(slot)).where(assembling)
        try:
            with self.session.begin_nested():
                result = self.session.execute(insert(SampleSetItemModel)
                                              .from_select(["sample_set_id", "sample_id", "slot"], row))
        except IntegrityError:
            if self._exists(SampleSetItemModel.sample_id == sample_id):
                raise SampleAlreadyInSet() from None
            if self._exists(SampleSetItemModel.sample_set_id == sample_set_id, SampleSetItemModel.slot == slot):
                raise SlotTaken() from None
            raise  # otro error (lote o muestra inexistente): no es un choque de lugar
        if result.rowcount == 0:
            raise SetNotAssembling()

    def _exists(self, *where) -> bool:
        return self.session.scalar(select(select(SampleSetItemModel.id).where(*where).exists()))

    def close(self, sample_set_id: int, now: datetime, is_urgent: bool = False) -> bool:
        sample_set = self.session.get(SampleSetModel, sample_set_id)
        if sample_set is None or sample_set.status != SampleSetStatus.ASSEMBLING.value:
            return False
        try:
            # Los cambios van dentro del savepoint: si otro pedido cerró el lote (otra `version`), se
            # deshace solo esto y la sesión sigue usable para el resto del pedido.
            with self.session.begin_nested():
                sample_set.status = SampleSetStatus.CLOSED.value
                sample_set.closed_at = now
                sample_set.is_urgent = sample_set.is_urgent or is_urgent
                self.session.flush()
        except StaleDataError:
            return False
        return True

    def study_for_sample(self, sample_id: int) -> int | None:
        return self.session.scalar(select(SampleModel.study_id).where(SampleModel.id == sample_id))

    def pompe_inputs(self, study_id: int) -> dict | None:
        # PROVISORIO (decisión 018): lectura directa de studies, study_pathologies y patients, como en turnos,
        # hasta que estudios y pacientes ofrezcan estos datos. Solo lectura.
        study = self.session.execute(select(StudyModel.created_at, Paciente.fecha_nacimiento)
                                     .join(Paciente, Paciente.id == StudyModel.patient_id)
                                     .where(StudyModel.id == study_id)).first()
        if study is None:
            return None
        codes = self.session.scalars(select(StudyPathologyModel.code)
                                     .where(StudyPathologyModel.study_id == study_id)).all()
        return {"pathology_codes": list(codes), "birth_date": study.fecha_nacimiento,
                "study_created_at": study.created_at}

    def _record(self, sample_set: SampleSetModel) -> dict:
        items = self.session.execute(select(SampleSetItemModel.slot, SampleSetItemModel.sample_id, SampleModel.study_id)
                                     .join(SampleModel, SampleModel.id == SampleSetItemModel.sample_id)
                                     .where(SampleSetItemModel.sample_set_id == sample_set.id)
                                     .order_by(SampleSetItemModel.slot)).all()
        return {"id": sample_set.id, "status": sample_set.status, "is_urgent": sample_set.is_urgent,
                "created_at": sample_set.created_at, "closed_at": sample_set.closed_at,
                "items": [{"slot": slot, "sample_id": sample_id, "study_id": study_id}
                          for slot, sample_id, study_id in items]}

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
