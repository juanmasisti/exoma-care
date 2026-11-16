from sqlalchemy import select

from app.infrastructure.database.models import Paciente
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.study_models import StudyModel

DEMO_PATIENT_DNI = "45000001"
BIOINFORMATICS_STATUS = "en_area_bioinformatica"


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
            select(StudyModel.id).where(
                StudyModel.patient_id == patient_id,
                StudyModel.status == BIOINFORMATICS_STATUS,
            )
        )
        if existing is not None:
            print(f"Estudio bioinformático DEMO existente: id={existing}.")
            return 0

        session.add(
            StudyModel(
                patient_id=patient_id,
                status=BIOINFORMATICS_STATUS,
            )
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
