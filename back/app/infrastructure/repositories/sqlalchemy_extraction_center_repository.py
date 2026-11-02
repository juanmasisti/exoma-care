from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.database.logistics_models import ExtractionCenterModel, HolidayModel, ProvinceModel


class SQLAlchemyExtractionCenterRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _record(center: ExtractionCenterModel) -> dict:
        return {"id": center.id, "name": center.name, "address": center.address, "city": center.city,
                "province_id": center.province_id, "latitude": center.latitude,
                "longitude": center.longitude, "phone": center.phone}

    def provinces(self) -> list[dict]:
        rows = self.session.execute(
            select(ProvinceModel.id, ProvinceModel.name, func.count(ExtractionCenterModel.id))
            .outerjoin(ExtractionCenterModel, and_(ExtractionCenterModel.province_id == ProvinceModel.id,
                                                   ExtractionCenterModel.active))
            .group_by(ProvinceModel.id).order_by(ProvinceModel.name)
        )
        return [{"id": id_, "name": name, "active_centers": count} for id_, name, count in rows]

    def active_centers(self, province_id: int | None, query: str) -> list[dict]:
        statement = select(ExtractionCenterModel).where(ExtractionCenterModel.active)
        if province_id is not None:
            statement = statement.where(ExtractionCenterModel.province_id == province_id)
        query = query.strip().lower()
        if query:
            statement = statement.where(or_(
                func.lower(ExtractionCenterModel.name).contains(query, autoescape=True),
                func.lower(ExtractionCenterModel.city).contains(query, autoescape=True),
            ))
        return [self._record(c) for c in self.session.scalars(statement.order_by(ExtractionCenterModel.name))]

    def get_active_center(self, center_id: int) -> dict | None:
        center = self.session.get(ExtractionCenterModel, center_id)
        return self._record(center) if center is not None and center.active else None

    def holiday(self, day: date) -> str | None:
        holiday = self.session.get(HolidayModel, day)
        return holiday.description if holiday is not None else None
