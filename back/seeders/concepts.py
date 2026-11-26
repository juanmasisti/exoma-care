"""Carga optativa de conceptos ficticios; no contiene terminología SNOMED."""
from sqlalchemy import select

from app.infrastructure.database.catalog_models import SymptomModel
from app.infrastructure.database.session import SessionLocal


def seed() -> None:
    with SessionLocal.begin() as session:
        for number in range(1, 5):
            code = f"DEMO-{number}"
            exists = session.scalar(
                select(SymptomModel.id).where(
                    SymptomModel.code_system == "DEMO",
                    SymptomModel.code == code,
                )
            )
            if exists is None:
                session.add(
                    SymptomModel(
                        code=code,
                        label=f"Síntoma de demostración {number}",
                        code_system="DEMO",
                    )
                )
    print("Conceptos DEMO preparados. No representan síntomas médicos reales.")
