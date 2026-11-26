"""Apply database migrations and populate selected idempotent demo seeders."""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from seeders import catalog, concepts, logistics, patients, studies, users

SEEDERS = {
    "users": users.seed,
    "patients": patients.seed,
    "catalog": catalog.seed,
    "concepts": concepts.seed,
    "logistics": logistics.seed,
    "studies": studies.seed,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrá SQLite (o DATABASE_URL configurada) y cargá datos DEMO."
    )
    parser.add_argument(
        "target",
        nargs="?",
        choices=["all", "catalog-upgrade", *SEEDERS],
        default="all",
        help="Seeder a ejecutar (por defecto: todos).",
    )
    parser.add_argument("--apply", action="store_true", help="Aplicar catalog-upgrade; sin esta opción solo inspecciona.")
    args = parser.parse_args()
    if args.target == "catalog-upgrade":
        from seeders.catalog_upgrade import run
        run(apply=args.apply)
        return
    if args.apply:
        parser.error("--apply solo corresponde a catalog-upgrade")

    back_dir = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(back_dir / "alembic.ini"))
    command.upgrade(alembic_config, "head")
    print("Migraciones aplicadas hasta head.")

    selected_seeders = [
        ("users", users.seed),
        ("patients", patients.seed),
        ("catalog", catalog.seed),
        ("logistics", logistics.seed),
        ("studies", studies.seed),
    ] if args.target == "all" else [
        (args.target, SEEDERS[args.target])
    ]
    for name, run_seeder in selected_seeders:
        print(f"Ejecutando seeder: {name}")
        run_seeder()


if __name__ == "__main__":
    main()
