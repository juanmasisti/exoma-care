from datetime import date

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.session import Base
from app.infrastructure.database.logistics_models import ExtractionCenterModel, HolidayModel, ProvinceModel
from app.infrastructure.database.seed_demo_extraction_centers import seed_demo_extraction_centers


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_first_run_creates_24_provinces_100_demo_centers_and_two_years_of_holidays(factory):
    assert seed_demo_extraction_centers(factory, year=2026) == (24, 100, 24)
    with factory() as session:
        centers = session.scalars(select(ExtractionCenterModel)).all()
        assert all("DEMO" in center.name and "DEMO" in center.address and "DEMO" in center.phone for center in centers)
        assert len({(center.latitude, center.longitude) for center in centers}) == 100
        assert all(center.active for center in centers)
        assert session.get(HolidayModel, date(2026, 4, 3)).description == "Viernes Santo"
        assert session.get(HolidayModel, date(2027, 12, 25)).description == "Navidad"


def test_second_run_adds_nothing(factory):
    seed_demo_extraction_centers(factory, year=2026)
    assert seed_demo_extraction_centers(factory, year=2026) == (0, 0, 0)
    with factory() as session:
        assert (count(session, ProvinceModel), count(session, ExtractionCenterModel), count(session, HolidayModel)) == (24, 100, 24)


def test_seed_keeps_existing_edits(factory):
    seed_demo_extraction_centers(factory, year=2026)
    with factory.begin() as session:
        center = session.scalars(select(ExtractionCenterModel)).first()
        center.active = False
        center_id = center.id
        session.get(HolidayModel, date(2026, 1, 1)).description = "Editado a mano"
    seed_demo_extraction_centers(factory, year=2026)
    with factory() as session:
        assert session.get(ExtractionCenterModel, center_id).active is False
        assert session.get(HolidayModel, date(2026, 1, 1)).description == "Editado a mano"
