"""Estudios DEMO para el paciente de prueba (DNI 45000001). PROVISORIO, como la tabla `studies`."""
from sqlalchemy import select

from app.infrastructure.database.models import Paciente
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.study_models import StudyModel

DEMO_PATIENT_DNI = "45000001"
DEMO_STATUSES = ("pagado", "autorizado", "pendiente_pago")


def seed_demo_studies(session_factory=SessionLocal):
    created = 0
    with session_factory.begin() as session:
        patient_id = session.scalar(select(Paciente.id).where(Paciente.dni == DEMO_PATIENT_DNI))
        if patient_id is None:
            print(f"Estudios DEMO: no existe el paciente con DNI {DEMO_PATIENT_DNI}; no se creó nada.")
            return 0
        existing = set(session.scalars(select(StudyModel.status).where(StudyModel.patient_id == patient_id)))
        for status in DEMO_STATUSES:
            if status not in existing:
                session.add(StudyModel(patient_id=patient_id, status=status))
                created += 1
    print(f"Estudios DEMO: {created} agregados al paciente {DEMO_PATIENT_DNI}; existentes conservados.")
    return created


if __name__ == "__main__":
    seed_demo_studies()
