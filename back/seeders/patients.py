from sqlalchemy import select

from app.domain.entities.roles import UserRole
from app.infrastructure.database.models import Paciente, UserModel
from app.infrastructure.database.session import SessionLocal

DEMO_PATIENT_DNI = "45000001"


def seed() -> int:
    with SessionLocal.begin() as session:
        patient = session.scalar(
            select(Paciente).where(Paciente.dni == DEMO_PATIENT_DNI)
        )
        if patient is not None:
            print(f"Paciente DEMO existente: DNI {DEMO_PATIENT_DNI}; sin cambios.")
            return 0

        account = session.scalar(
            select(UserModel).where(
                UserModel.national_id == DEMO_PATIENT_DNI,
                UserModel.role == UserRole.PATIENT,
            )
        )
        if account is None:
            print("Paciente DEMO: falta la cuenta de paciente; ejecutá users primero.")
            return 0

        session.add(
            Paciente(
                dni=DEMO_PATIENT_DNI,
                nombre=account.first_name,
                apellido=account.last_name,
                fecha_nacimiento=account.date_of_birth,
                telefono=account.phone,
                usuario_id=account.id,
                email=account.email,
                version=1,
            )
        )
    print(f"Paciente DEMO creado y vinculado a la cuenta {account.username}.")
    return 1
