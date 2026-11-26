from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.entities.logistics import SampleSetStatus
from app.infrastructure.database.logistics_models import SampleModel, SampleSetItemModel, SampleSetModel
from app.infrastructure.database.study_models import StudyModel


class SQLAlchemyShipmentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, sample_set_id: int) -> dict | None:
        # populate_existing: lee la fila de nuevo aunque la sesión ya la tenga (otro pedido pudo cambiarla).
        # Pisa cambios sin flush del mismo lote: llamarlo antes de modificarlo, no después.
        sample_set = self.session.get(SampleSetModel, sample_set_id, populate_existing=True)
        if sample_set is None:
            return None
        sample_ids = self.session.scalars(select(SampleSetItemModel.sample_id)
                                          .where(SampleSetItemModel.sample_set_id == sample_set_id)
                                          .order_by(SampleSetItemModel.slot)).all()
        return {"id": sample_set.id, "status": sample_set.status, "closed_at": sample_set.closed_at,
                "csv_path": sample_set.csv_path, "authorization_pdf_path": sample_set.authorization_pdf_path,
                "pickup_at": sample_set.pickup_at, "courier_pickup_id": sample_set.courier_pickup_id,
                "sample_ids": list(sample_ids)}

    def closed_without_authorization(self) -> list[int]:
        return list(self.session.scalars(select(SampleSetModel.id)
                                         .where(SampleSetModel.status == SampleSetStatus.CLOSED.value,
                                                SampleSetModel.authorization_pdf_path.is_(None))
                                         .order_by(SampleSetModel.id)))

    def awaiting_pickup(self) -> list[int]:
        return list(self.session.scalars(select(SampleSetModel.id)
                                         .where(SampleSetModel.status == SampleSetStatus.AWAITING_PICKUP.value)
                                         .order_by(SampleSetModel.id)))

    def items(self, sample_set_id: int) -> list[dict]:
        # PROVISORIO (como en la decisión 013): lee studies.patient_id hasta que estudios lo ofrezca. Solo lectura.
        rows = self.session.execute(select(SampleSetItemModel.sample_id, SampleModel.study_id, StudyModel.patient_id)
                                    .join(SampleModel, SampleModel.id == SampleSetItemModel.sample_id)
                                    .join(StudyModel, StudyModel.id == SampleModel.study_id)
                                    .where(SampleSetItemModel.sample_set_id == sample_set_id)
                                    .order_by(SampleSetItemModel.slot))
        return [{"sample_id": sample_id, "study_id": study_id, "patient_id": patient_id}
                for sample_id, study_id, patient_id in rows]

    def save_authorization(self, sample_set_id: int, csv_path: str, authorization_pdf_path: str) -> bool:
        return self._change(sample_set_id, (SampleSetModel.status == SampleSetStatus.CLOSED.value,
                                            SampleSetModel.authorization_pdf_path.is_(None)),
                            csv_path=csv_path, authorization_pdf_path=authorization_pdf_path)

    def schedule_pickup(self, sample_set_id: int, courier_pickup_id: str, pickup_at: datetime) -> bool:
        return self._change(sample_set_id, (SampleSetModel.status == SampleSetStatus.CLOSED.value,
                                            SampleSetModel.authorization_pdf_path.is_not(None)),
                            status=SampleSetStatus.AWAITING_PICKUP.value, courier_pickup_id=courier_pickup_id,
                            pickup_at=pickup_at)

    def mark_in_transit(self, sample_set_id: int) -> bool:
        return self._change(sample_set_id, (SampleSetModel.status == SampleSetStatus.AWAITING_PICKUP.value,),
                            status=SampleSetStatus.IN_TRANSIT_TO_SEQUENCING_LAB.value)

    def _change(self, sample_set_id: int, expected, **values) -> bool:
        # UPDATE condicional y no un savepoint como `close`: en SQLite, un savepoint sin una escritura previa
        # confirma solo y el rollback del pedido no lo deshace (decisión 019). Sube la `version` del lote
        # para que un cambio de T05 leído antes falle.
        result = self.session.execute(update(SampleSetModel)
                                      .where(SampleSetModel.id == sample_set_id, *expected)
                                      .values(**values, version=SampleSetModel.version + 1))
        return result.rowcount == 1

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
