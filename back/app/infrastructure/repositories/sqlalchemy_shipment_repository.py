from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.logistics import SampleSetStatus
from app.infrastructure.database.logistics_models import SampleSetItemModel, SampleSetModel


class SQLAlchemyShipmentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, sample_set_id: int) -> dict | None:
        sample_set = self.session.get(SampleSetModel, sample_set_id)
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

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
