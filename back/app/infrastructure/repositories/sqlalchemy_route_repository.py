from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities.logistics import DailyRouteStatus, SampleStatus
from app.domain.interfaces.route_repository import RouteAlreadyExists
from app.infrastructure.database.logistics_models import (
    AppointmentModel, DailyRouteModel, ExtractionCenterModel, ProvinceModel, RouteStopModel, SampleModel,
)


class SQLAlchemyRouteRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, route_id: int) -> dict | None:
        route = self.session.get(DailyRouteModel, route_id)
        return self._record(route) if route is not None else None

    def route_for(self, day: date, province_id: int) -> dict | None:
        route = self.session.scalar(select(DailyRouteModel).where(DailyRouteModel.date == day,
                                                                  DailyRouteModel.province_id == province_id))
        return self._record(route) if route is not None else None

    def add_route(self, day: date, province_id: int, transporter_id: int | None, center_ids: list[int]) -> int:
        route = DailyRouteModel(date=day, province_id=province_id, transporter_id=transporter_id,
                                status=DailyRouteStatus.PENDING.value)
        try:
            # Savepoint: si la orden ya existe se deshace solo esto, no el resto del pedido.
            with self.session.begin_nested():
                self.session.add(route)
                self.session.flush()
                self.session.add_all(RouteStopModel(route_id=route.id, center_id=center_id, sequence=sequence)
                                     for sequence, center_id in enumerate(center_ids, start=1))
        except IntegrityError:
            if self.route_for(day, province_id) is not None:
                raise RouteAlreadyExists() from None
            raise  # otro error (centro repetido o inexistente): no es una orden ya generada
        return route.id

    def centers_with_ready_samples(self) -> dict[int, list[int]]:
        # Solo centros activos: la API de recorridos no ordena centros dados de baja (RoutePreviewService).
        rows = self.session.execute(
            select(ExtractionCenterModel.province_id, ExtractionCenterModel.id).distinct()
            .join(AppointmentModel, AppointmentModel.center_id == ExtractionCenterModel.id)
            .join(SampleModel, SampleModel.appointment_id == AppointmentModel.id)
            .where(SampleModel.status == SampleStatus.READY_FOR_PICKUP.value, ExtractionCenterModel.active.is_(True))
            .order_by(ExtractionCenterModel.province_id, ExtractionCenterModel.id)
        )
        centers = {}
        for province_id, center_id in rows:
            centers.setdefault(province_id, []).append(center_id)
        return centers

    def routes_for_day(self, day: date) -> list[dict]:
        rows = self.session.execute(
            select(DailyRouteModel, ProvinceModel.name, func.count(RouteStopModel.id),
                   func.count(RouteStopModel.picked_up_at))
            .join(ProvinceModel, ProvinceModel.id == DailyRouteModel.province_id)
            .outerjoin(RouteStopModel, RouteStopModel.route_id == DailyRouteModel.id)
            .where(DailyRouteModel.date == day)
            .group_by(DailyRouteModel.id, ProvinceModel.name).order_by(ProvinceModel.name)
        )
        return [{"id": route.id, "date": route.date, "province_id": route.province_id, "province": province,
                 "status": route.status, "arrived_at": route.arrived_at, "stops": stops, "picked_up": picked_up}
                for route, province, stops, picked_up in rows]

    def _record(self, route: DailyRouteModel) -> dict:
        stops = self.session.scalars(select(RouteStopModel).where(RouteStopModel.route_id == route.id)
                                     .order_by(RouteStopModel.sequence)).all()
        return {"id": route.id, "date": route.date, "province_id": route.province_id,
                "transporter_id": route.transporter_id, "status": route.status, "arrived_at": route.arrived_at,
                "stops": [{"id": stop.id, "center_id": stop.center_id, "sequence": stop.sequence,
                           "picked_up_at": stop.picked_up_at} for stop in stops]}

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
