"""Cinco patologías iniciales con asociaciones DEMO del prototipo, no SNOMED."""
import json
from pathlib import Path
import unicodedata

from sqlalchemy import select

from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel
from app.infrastructure.database.session import SessionLocal


def seed_demo_pathologies(session_factory=SessionLocal):
    data = json.loads(Path(__file__).with_name("demo_pathologies.json").read_text(encoding="utf-8"))
    created = 0
    with session_factory.begin() as session:
        for entry in data["pathologies"]:
            concepts = []
            for term in [entry["cardinal"], *entry["secondary"]]:
                concept = session.scalar(select(SymptomModel).where(
                    SymptomModel.code_system == "DEMO", SymptomModel.code == term["code"],
                ))
                if concept is None:
                    concept = SymptomModel(code=term["code"], label=term["label"], code_system="DEMO")
                    session.add(concept)
                    session.flush()
                concepts.append(concept)
            normalized = unicodedata.normalize("NFKC", entry["name"]).casefold()
            existing = session.scalar(select(PathologyModel.id).where(
                PathologyModel.normalized_name == normalized,
            ))
            if existing is None:
                session.add(PathologyModel(name=entry["name"], normalized_name=normalized,
                                           cardinal_symptom=concepts[0], secondary_symptoms=concepts[1:]))
                session.flush()
                created += 1
    print(f"Catálogo DEMO preparado: {created} patologías agregadas; existentes conservadas.")
    return created


if __name__ == "__main__":
    seed_demo_pathologies()
