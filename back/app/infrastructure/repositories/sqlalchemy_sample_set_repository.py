from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.orm import Session

from app.domain.entities.logistics import SAMPLE_SET_SIZE, SampleSetStatus
from app.domain.interfaces.sample_set_repository import (
    AssemblingSetExists, SampleAlreadyInSet, SetFull, SetNotAssembling, SlotTaken,
)
from app.infrastructure.database.logistics_models import SampleModel, SampleSetItemModel, SampleSetModel
from app.infrastructure.database.models import Paciente
from app.infrastructure.database.study_models import StudyModel, StudyPathologyModel

ASSEMBLING = SampleSetStatus.ASSEMBLING.value


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
                                         .where(SampleSetModel.status == ASSEMBLING))
        return self._record(sample_set) if sample_set is not None else None

    # Sin savepoints: pysqlite abre la transacción recién con un INSERT/UPDATE/DELETE, así que un SAVEPOINT como
    # primera escritura la confirmaba al soltarse y el rollback del pedido ya no lo deshacía (decisión 018). Cada
    # operación es una sola sentencia condicional: un choque no inserta ni cambia filas, y no rompe la transacción.

    def open_set(self, is_urgent: bool, now: datetime) -> int:
        table = SampleSetModel.__table__
        no_assembling = ~select(SampleSetModel.id).where(SampleSetModel.status == ASSEMBLING).exists()
        row = select(literal(ASSEMBLING), literal(is_urgent, table.c.is_urgent.type),
                     literal(now, table.c.created_at.type), literal(1, table.c.version.type)).where(no_assembling)
        # El índice único parcial queda de respaldo: con SQLite la sentencia se escribe entera, de a una.
        columns = ["status", "is_urgent", "created_at", "version"]
        sample_set_id = self.session.scalar(insert(table).from_select(columns, row).returning(table.c.id))
        if sample_set_id is None:
            raise AssemblingSetExists()
        return sample_set_id

    def add_item(self, sample_set_id: int, sample_id: int, slot: int) -> None:
        if not 1 <= slot <= SAMPLE_SET_SIZE:
            raise SetFull()
        # Solo entra si el lote sigue armándose al escribir (un cierre que ganó antes, como un Pompe urgente, no
        # deja sumar muestras) y si el lugar y la muestra están libres.
        assembling = select(SampleSetModel.id).where(SampleSetModel.id == sample_set_id,
                                                     SampleSetModel.status == ASSEMBLING).exists()
        slot_taken = self._item(SampleSetItemModel.sample_set_id == sample_set_id, SampleSetItemModel.slot == slot)
        sample_taken = self._item(SampleSetItemModel.sample_id == sample_id)
        row = (select(literal(sample_set_id), literal(sample_id), literal(slot))
               .where(assembling, ~slot_taken, ~sample_taken))
        # Una muestra inexistente sigue dando IntegrityError (clave foránea): no es un choque de lugar.
        columns = ["sample_set_id", "sample_id", "slot"]
        result = self.session.execute(insert(SampleSetItemModel).from_select(columns, row))
        if result.rowcount == 1:
            return
        if not self.session.scalar(select(assembling)):
            raise SetNotAssembling()
        if self.session.scalar(select(sample_taken)):
            raise SampleAlreadyInSet()
        raise SlotTaken()

    def _item(self, *where):
        return select(SampleSetItemModel.id).where(*where).exists()

    def close(self, sample_set_id: int, now: datetime, is_urgent: bool = False) -> bool:
        values = {"status": SampleSetStatus.CLOSED.value, "closed_at": now, "version": SampleSetModel.version + 1}
        if is_urgent:
            values["is_urgent"] = True
        # Condicional: solo cierra un lote que sigue armándose. "fetch" actualiza el lote si ya estaba en la sesión.
        result = self.session.execute(update(SampleSetModel)
                                      .where(SampleSetModel.id == sample_set_id, SampleSetModel.status == ASSEMBLING)
                                      .values(**values).execution_options(synchronize_session="fetch"))
        return result.rowcount == 1

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
