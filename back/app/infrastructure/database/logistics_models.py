"""Centros de extracción tercerizados, sus provincias, los feriados y los turnos del turnero."""
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, TypeDecorator, UniqueConstraint, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class UTCDateTime(TypeDecorator):
    """Guarda en UTC y devuelve con zona UTC.

    SQLite descarta la zona sin convertir: sin esto, 12:00-03:00 y 15:00 UTC quedarían
    distintos y el índice único de horarios no los vería como el mismo turno.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("La fecha y hora debe indicar la zona horaria.")
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ProvinceModel(Base):
    __tablename__ = "provinces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)


class ExtractionCenterModel(Base):
    __tablename__ = "extraction_centers"
    __table_args__ = (UniqueConstraint("province_id", "name", name="uq_extraction_center_province_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    phone: Mapped[str | None] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(server_default=true())


class HolidayModel(Base):
    __tablename__ = "holidays"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    description: Mapped[str] = mapped_column(String(120))


BOOKED_ONLY = text("status = 'booked'")


class AppointmentModel(Base):
    __tablename__ = "appointments"
    # Unicidad solo entre turnos vigentes: un cancelado no ocupa el horario ni el estudio.
    __table_args__ = (
        Index("uq_appointments_center_slot_booked", "center_id", "starts_at", unique=True,
              sqlite_where=BOOKED_ONLY, postgresql_where=BOOKED_ONLY),
        Index("uq_appointments_study_booked", "study_id", unique=True,
              sqlite_where=BOOKED_ONLY, postgresql_where=BOOKED_ONLY),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"))
    center_id: Mapped[int] = mapped_column(ForeignKey("extraction_centers.id"))
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20))
    # Estado del estudio al reservar (pagado/autorizado), para restaurarlo al cancelar.
    study_status_before: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
