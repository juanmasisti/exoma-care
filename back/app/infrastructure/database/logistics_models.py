"""Centros de extracción tercerizados, sus provincias y los feriados del turnero."""
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


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
