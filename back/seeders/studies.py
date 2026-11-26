from sqlalchemy import select

from app.infrastructure.database.models import Paciente
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.study_models import StudyGeneModel, StudyModel

DEMO_PATIENT_DNI = "45000001"
BIOINFORMATICS_STATUS = "en_area_bioinformatica"
BIOINFORMATICS_STATUSES = (BIOINFORMATICS_STATUS, "en_analisis")
DEMO_GENES = ("GAA", "GBA")


def seed_bioinformatics_study(session_factory=SessionLocal) -> int:
    with session_factory.begin() as session:
        patient_id = session.scalar(
            select(Paciente.id).where(Paciente.dni == DEMO_PATIENT_DNI)
        )
        if patient_id is None:
            print(
                "Estudio bioinformático DEMO: falta el paciente de prueba; "
                "ejecutá primero el seeder de usuarios."
            )
            return 0

        existing = session.scalar(
            select(StudyModel).where(
                StudyModel.patient_id == patient_id,
                StudyModel.status.in_(BIOINFORMATICS_STATUSES),
            ).order_by(StudyModel.id.desc())
        )
        if existing is not None:
            existing_genes = set(
                session.scalars(
                    select(StudyGeneModel.symbol).where(
                        StudyGeneModel.study_id == existing.id
                    )
                )
            )
            session.add_all(
                StudyGeneModel(
                    study_id=existing.id,
                    symbol=symbol,
                    origin="manual",
                )
                for symbol in DEMO_GENES
                if symbol not in existing_genes
            )
            print(f"Estudio bioinformático DEMO existente: id={existing.id}.")
            return 0

        study = StudyModel(
            patient_id=patient_id,
            status=BIOINFORMATICS_STATUS,
        )
        session.add(study)
        session.flush()
        session.add_all(
            StudyGeneModel(study_id=study.id, symbol=symbol, origin="manual")
            for symbol in DEMO_GENES
        )
    print("Estudio bioinformático DEMO creado y disponible para ser tomado.")
    return 1


def seed() -> tuple[int, int]:
    created = seed_demo_studies()
    bioinformatics_created = seed_bioinformatics_study()
    return created, bioinformatics_created


def seed_demo_studies(session_factory=SessionLocal) -> int:
    created = 0
    with session_factory.begin() as session:
        patient_id = session.scalar(
            select(Paciente.id).where(Paciente.dni == DEMO_PATIENT_DNI)
        )
        if patient_id is None:
            print(
                f"Estudios DEMO: no existe el paciente con DNI {DEMO_PATIENT_DNI}; "
                "no se creó nada."
            )
            return 0
        existing = set(
            session.scalars(
                select(StudyModel.status).where(StudyModel.patient_id == patient_id)
            )
        )
        for status in ("pagado", "autorizado", "pendiente_pago"):
            if status not in existing:
                session.add(StudyModel(patient_id=patient_id, status=status))
                created += 1
    print(
        f"Estudios DEMO: {created} agregados al paciente {DEMO_PATIENT_DNI}; "
        "existentes conservados."
    )
    return created
