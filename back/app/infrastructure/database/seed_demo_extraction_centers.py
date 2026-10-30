"""Provincias reales con centros de extracción ficticios (DEMO) y feriados fijos."""
from datetime import datetime
import json
from pathlib import Path

from sqlalchemy import select

from app.domain.entities.logistics import TIMEZONE, fixed_national_holidays
from app.infrastructure.database.logistics_models import ExtractionCenterModel, HolidayModel, ProvinceModel
from app.infrastructure.database.session import SessionLocal

# Unos 200 m por centro: no se superponen en el mapa y quedan dentro de la ciudad.
CENTER_OFFSET_DEGREES = 0.002


def seed_demo_extraction_centers(session_factory=SessionLocal, year=None):
    data = json.loads(Path(__file__).with_name("demo_extraction_centers.json").read_text(encoding="utf-8"))
    year = year or datetime.now(TIMEZONE).year
    provinces_created = centers_created = holidays_created = 0
    with session_factory.begin() as session:
        for entry in data["provinces"]:
            province = session.scalar(select(ProvinceModel).where(ProvinceModel.name == entry["name"]))
            if province is None:
                province = ProvinceModel(name=entry["name"])
                session.add(province)
                session.flush()
                provinces_created += 1
            for number in range(1, entry["centers"] + 1):
                name = f"Centro de extracción DEMO {entry['capital']} {number}"
                existing = session.scalar(select(ExtractionCenterModel.id).where(
                    ExtractionCenterModel.province_id == province.id, ExtractionCenterModel.name == name,
                ))
                if existing is None:
                    lat_sign, lon_sign = entry["offset"]
                    offset = CENTER_OFFSET_DEGREES * number
                    session.add(ExtractionCenterModel(
                        name=name, address=f"Calle DEMO {number}, {entry['capital']}", city=entry["capital"],
                        province_id=province.id, latitude=round(entry["latitude"] + lat_sign * offset, 6),
                        longitude=round(entry["longitude"] + lon_sign * offset, 6), phone=f"DEMO-0000-{number:02d}",
                    ))
                    centers_created += 1
        for holiday_year in (year, year + 1):
            for day, description in fixed_national_holidays(holiday_year).items():
                if session.get(HolidayModel, day) is None:
                    session.add(HolidayModel(day=day, description=description))
                    holidays_created += 1
    print(f"Centros DEMO: {provinces_created} provincias, {centers_created} centros y "
          f"{holidays_created} feriados agregados; existentes conservados.")
    return provinces_created, centers_created, holidays_created


if __name__ == "__main__":
    seed_demo_extraction_centers()
