"""Restablece la contraseña de un usuario DEMO (correo @exoma.test) para probar en local.

El seeder genera la contraseña del paciente al azar y la muestra una sola vez; si se perdió,
este script la deja en un valor conocido. Solo funciona con cuentas DEMO.

Uso (desde back/, con el entorno virtual activo):
    python -m scripts.reset_demo_password sofia.ramirez@exoma.test
    python -m scripts.reset_demo_password sofia.ramirez@exoma.test --password "OtraClave123!"
"""

import argparse

from sqlalchemy import select

from app.infrastructure.database.models import UserModel
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.session import SessionLocal

DEMO_DOMAIN = "@exoma.test"
DEFAULT_PASSWORD = "Exoma2024!"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email", help="Correo de la cuenta DEMO (termina en @exoma.test).")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"Nueva contraseña (por defecto {DEFAULT_PASSWORD}).")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not email.endswith(DEMO_DOMAIN):
        parser.error(f"Solo se restablecen cuentas DEMO ({DEMO_DOMAIN}).")

    with SessionLocal.begin() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == email))
        if user is None:
            parser.error("No existe una cuenta con ese correo; ejecutá primero: python -m seeders")
        user.password_hash = hash_password(args.password)
    print(f"Contraseña actualizada para {email}.")


if __name__ == "__main__":
    main()
