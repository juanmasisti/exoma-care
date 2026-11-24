from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Date, Integer, String, func, insert, literal, select, update
from sqlalchemy.orm import Session

from app.domain.entities.logistics import TIMEZONE, DailyRouteStatus, SampleStatus, study_code
from app.domain.interfaces.route_repository import RouteAlreadyExists
from app.infrastructure.database.logistics_models import (
    AppointmentModel, DailyRouteModel, ExtractionCenterModel, ProvinceModel, RoutePickupModel, RouteStopModel,
    SampleModel, UTCDateTime,
)


def _local(at: datetime | None) -> datetime | None:
    # En hora de Argentina, como el resto de las respuestas de logística: el front la muestra sin convertir.
    return at.astimezone(TIMEZONE) if at is not None else None


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
        # INSERT condicional y no un savepoint: en SQLite, un savepoint antes de cualquier escritura del pedido
        # se confirma solo y el rollback no lo deshace. El NOT EXISTS corre con el lock de escritura tomado; si
        # igual saltara el índice único (otro motor), el pedido falla entero.
        same_route = (DailyRouteModel.date == day, DailyRouteModel.province_id == province_id)
        values = select(literal(day, Date), literal(province_id, Integer), literal(transporter_id, Integer),
                        literal(DailyRouteStatus.PENDING.value, String), literal(datetime.now(UTC), UTCDateTime)
                        ).where(~select(DailyRouteModel.id).where(*same_route).exists())
        result = self.session.execute(insert(DailyRouteModel).from_select(
            ["date", "province_id", "transporter_id", "status", "created_at"], values))
        if result.rowcount == 0:
            raise RouteAlreadyExists()
        route_id = self.session.scalar(select(DailyRouteModel.id).where(*same_route))
        # Un centro repetido o inexistente es IntegrityError y aborta el pedido entero, sin confirmar nada.
        self.session.add_all(RouteStopModel(route_id=route_id, center_id=center_id, sequence=sequence)
                             for sequence, center_id in enumerate(center_ids, start=1))
        self.session.flush()
        return route_id

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
                 "status": route.status, "arrived_at": _local(route.arrived_at), "stops": stops, "picked_up": picked_up}
                for route, province, stops, picked_up in rows]

    def route_detail(self, route_id: int) -> dict | None:
        row = self.session.execute(select(DailyRouteModel, ProvinceModel.name)
                                   .join(ProvinceModel, ProvinceModel.id == DailyRouteModel.province_id)
                                   .where(DailyRouteModel.id == route_id)).first()
        if row is None:
            return None
        route, province = row
        stops = self.session.execute(
            select(RouteStopModel, ExtractionCenterModel)
            .join(ExtractionCenterModel, ExtractionCenterModel.id == RouteStopModel.center_id)
            .where(RouteStopModel.route_id == route_id).order_by(RouteStopModel.sequence)
        ).all()
        return {"id": route.id, "date": route.date, "province_id": route.province_id, "province": province,
                "status": route.status, "arrived_at": _local(route.arrived_at),
                "stops": [{"id": stop.id, "sequence": stop.sequence, "picked_up_at": _local(stop.picked_up_at),
                           "center": {"id": center.id, "name": center.name, "address": center.address,
                                      "city": center.city},
                           **self._stop_samples(stop)}
                          for stop, center in stops]}

    def _stop_samples(self, stop: RouteStopModel) -> dict:
        # Antes del retiro, las que el centro tiene listas ahora; después, exactamente las que se retiraron.
        if stop.picked_up_at is None:
            query = (select(SampleModel.id, SampleModel.study_id)
                     .join(AppointmentModel, AppointmentModel.id == SampleModel.appointment_id)
                     .where(AppointmentModel.center_id == stop.center_id,
                            SampleModel.status == SampleStatus.READY_FOR_PICKUP.value))
        else:
            query = (select(SampleModel.id, SampleModel.study_id)
                     .join(RoutePickupModel, RoutePickupModel.sample_id == SampleModel.id)
                     .where(RoutePickupModel.stop_id == stop.id))
        rows = self.session.execute(query.order_by(SampleModel.id)).all()
        return {"sample_ids": [sample_id for sample_id, _ in rows],
                "sample_codes": [study_code(study_id) for _, study_id in rows]}

    def mark_stop_picked(self, stop_id: int, at: datetime) -> bool:
        # Condicional: de dos retiros a la vez del mismo centro, solo uno lo marca.
        result = self.session.execute(update(RouteStopModel)
                                      .where(RouteStopModel.id == stop_id, RouteStopModel.picked_up_at.is_(None))
                                      .values(picked_up_at=at))
        return result.rowcount == 1

    def add_pickups(self, stop_id: int, sample_ids: list[int]) -> None:
        self.session.add_all(RoutePickupModel(stop_id=stop_id, sample_id=sample_id) for sample_id in sample_ids)
        self.session.flush()

    def mark_arrived(self, route_id: int, at: datetime) -> bool:
        result = self.session.execute(update(DailyRouteModel)
                                      .where(DailyRouteModel.id == route_id,
                                             DailyRouteModel.status == DailyRouteStatus.PENDING.value)
                                      .values(status=DailyRouteStatus.ARRIVED.value, arrived_at=at))
        return result.rowcount == 1

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
