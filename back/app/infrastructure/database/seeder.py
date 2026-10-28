import secrets
from datetime import date

from sqlalchemy import select

from app.infrastructure.database.models import UserModel, UserRole
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.session import Base, SessionLocal, engine

DEFAULT_PASSWORD = "Exoma2024!"

INITIAL_USERS = (
    {
        "username": "dra.maria.gomez",
        "role": UserRole.TREATING_PHYSICIAN,
        "first_name": "María",
        "last_name": "Gómez",
        "phone": "+54 11 4000 0001",
        "email": "maria.gomez@exoma.test",
        "license_number": "MN-TEST-1001",
        "specialty": "Genética médica",
    },
    {
        "username": "ana.torres",
        "role": UserRole.LAB_ADMINISTRATOR,
        "first_name": "Ana",
        "last_name": "Torres",
        "phone": "+54 11 4000 0002",
        "email": "ana.torres@exoma.test",
    },
    {
        "username": "lucas.fernandez",
        "role": UserRole.BIOINFORMATICIAN,
        "first_name": "Lucas",
        "last_name": "Fernández",
        "phone": "+54 11 4000 0003",
        "email": "lucas.fernandez@exoma.test",
    },
    {
        "username": "carla.mendez",
        "role": UserRole.MEDICAL_MANAGER,
        "first_name": "Carla",
        "last_name": "Méndez",
        "phone": "+54 11 4000 0004",
        "email": "carla.mendez@exoma.test",
    },
    {
        "username": "paciente-45000001",
        "role": UserRole.PATIENT,
        "first_name": "Sofía",
        "last_name": "Ramírez",
        "phone": "+54 11 4000 0005",
        "email": "sofia.ramirez@exoma.test",
        "national_id": "45000001",
        "date_of_birth": date(1990, 5, 14),
    },
)


def seed_users() -> None:
    Base.metadata.create_all(bind=engine)
    created = 0
    skipped = 0
    patient_credentials: tuple[str, str] | None = None

    with SessionLocal.begin() as session:
        for user_data in INITIAL_USERS:
            duplicate = session.scalar(
                select(UserModel).where(UserModel.email == user_data["email"])
            )
            national_id = user_data.get("national_id")
            if duplicate is None and national_id is not None:
                duplicate = session.scalar(
                    select(UserModel).where(UserModel.national_id == national_id)
                )

            if duplicate is not None:
                skipped += 1
                continue

            is_patient = user_data["role"] is UserRole.PATIENT
            password = secrets.token_urlsafe(18) if is_patient else DEFAULT_PASSWORD
            new_user_data = {
                **user_data,
                "role": user_data["role"].value,
                "password_hash": hash_password(password),
            }
            user = UserModel(**new_user_data)
            session.add(user)
            created += 1

            if is_patient:
                patient_credentials = (user.username, password)

    print(f"Seeder finalizado: {created} usuario(s) creado(s), {skipped} omitido(s).")
    if patient_credentials is not None:
        username, password = patient_credentials
        print("Credenciales de prueba del paciente (guárdalas; no se volverán a mostrar):")
        print(f"  Usuario: {username}")
        print(f"  Contraseña temporal: {password}")
    if created:
        print(f"Contraseña inicial de los usuarios no pacientes: {DEFAULT_PASSWORD}")


if __name__ == "__main__":
    seed_users()
