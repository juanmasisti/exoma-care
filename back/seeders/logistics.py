"""Provincias reales con centros de extracción ficticios (DEMO), feriados fijos y turnos DEMO."""
import asyncio
from datetime import datetime, time, timedelta
import json
from pathlib import Path

from sqlalchemy import select

from app.domain.entities.logistics import TIMEZONE, fixed_national_holidays
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.database.logistics_models import (
    ExtractionCenterModel,
    HolidayModel,
    ProvinceModel,
)
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import (
    SQLAlchemyExtractionCenterRepository,
)
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.infrastructure.repositories.sqlalchemy_study_request_repository import SqlAlchemyStudyRequestRepository
from app.use_cases.appointments import AppointmentConflict, AppointmentService, InvalidSlot
from app.use_cases.studies import StudyService
from app.use_cases.study_payments import StudyPaymentService
from app.use_cases.study_requests import StudyRequestService

CENTER_OFFSET_DEGREES = 0.002


DEMO_PATIENT_DNI = "45000001"
DEMO_BOOKED_STUDIES = 3
DEMO_SLOT_TIME = time(10, 0)
MAX_DAYS_AHEAD = 60


def seed() -> tuple[tuple[int, int, int], int]:
    return seed_demo_extraction_centers(), seed_demo_booked_studies()


def seed_demo_extraction_centers(session_factory=SessionLocal, year=None):
    data = json.loads(
        Path(__file__)
        .with_name("demo_extraction_centers.json")
        .read_text(encoding="utf-8")
    )
    year = year or datetime.now(TIMEZONE).year
    provinces_created = centers_created = holidays_created = 0
    with session_factory.begin() as session:
        for entry in data["provinces"]:
            province = session.scalar(
                select(ProvinceModel).where(ProvinceModel.name == entry["name"])
            )
            if province is None:
                province = ProvinceModel(name=entry["name"])
                session.add(province)
                session.flush()
                provinces_created += 1
            for number in range(1, entry["centers"] + 1):
                name = f"Centro de extracción DEMO {entry['capital']} {number}"
                existing = session.scalar(
                    select(ExtractionCenterModel.id).where(
                        ExtractionCenterModel.province_id == province.id,
                        ExtractionCenterModel.name == name,
                    )
                )
                if existing is None:
                    lat_sign, lon_sign = entry["offset"]
                    offset = CENTER_OFFSET_DEGREES * number
                    session.add(
                        ExtractionCenterModel(
                            name=name,
                            address=f"Calle DEMO {number}, {entry['capital']}",
                            city=entry["capital"],
                            province_id=province.id,
                            latitude=round(entry["latitude"] + lat_sign * offset, 6),
                            longitude=round(entry["longitude"] + lon_sign * offset, 6),
                            phone=f"DEMO-0000-{number:02d}",
                        )
                    )
                    centers_created += 1
        for holiday_year in (year, year + 1):
            for day, description in fixed_national_holidays(holiday_year).items():
                if session.get(HolidayModel, day) is None:
                    session.add(HolidayModel(day=day, description=description))
                    holidays_created += 1
    print(
        f"Centros DEMO: {provinces_created} provincias, {centers_created} centros "
        f"y {holidays_created} feriados agregados; existentes conservados."
    )
    return provinces_created, centers_created, holidays_created


class DemoGeneCatalog:
    """Catálogo de genes fijo para el seeder: Fabry (catálogo DEMO de Juanma) sin salir a Apigen."""

    async def listar_patologias(self):
        return [{"codigo": "fabry", "nombre": "Enfermedad de Fabry", "genes": ["GLA"]}]

    async def buscar_genes(self, prefijo, limit=20):
        return []


def seed_demo_booked_studies(session_factory=SessionLocal, now=None) -> int:
    """Deja a la paciente DEMO con 3 estudios con turno reservado, para el simulador del bot (T03d).

    Cuenta sus turnos reservados (vengan de donde vengan) y crea los estudios que falten con el
    flujo de estudios (solicitud, presupuesto y pago particular simulado) y la reserva de turnos.
    """
    now = now or datetime.now(TIMEZONE)
    with session_factory() as session:
        patient = session.scalar(select(Paciente).where(Paciente.dni == DEMO_PATIENT_DNI))
        physician_id = patient.created_by_physician_id if patient else None
        physician_id = physician_id or _first_user(session, UserRole.TREATING_PHYSICIAN)
        admin_id = _first_user(session, UserRole.LAB_ADMINISTRATOR)
        center_id = session.scalar(select(ExtractionCenterModel.id).where(
            ExtractionCenterModel.name.like("Centro de extracción DEMO %")).order_by(ExtractionCenterModel.id))
        if patient is None or patient.usuario_id is None or None in (physician_id, admin_id, center_id):
            print("Turnos DEMO: falta la paciente DEMO con usuario, un médico, un administrativo o un centro DEMO; "
                  "no se creó nada.")
            return 0
        appointments = SQLAlchemyAppointmentRepository(session)
        missing = DEMO_BOOKED_STUDIES - len(appointments.booked_for_user(patient.usuario_id))
        if missing <= 0:
            print("Turnos DEMO: la paciente DEMO ya tiene sus turnos reservados.")
            return 0
        studies = SqlAlchemyStudyRequestRepository(session)
        requests = StudyRequestService(studies, DemoGeneCatalog())
        # Particular y sin cupón: no se consultan obras sociales ni cupones.
        payments = StudyPaymentService(studies, insurance=None, coupons=None)
        booking = AppointmentService(appointments, SQLAlchemyExtractionCenterRepository(session),
                                     StudyService(SQLAlchemyStudyRepository(session)))
        patient_user = AuthenticatedUser(patient.usuario_id, "", UserRole.PATIENT)
        day = now.date()
        for _ in range(missing):
            study = asyncio.run(requests.crear(physician_id=physician_id, patient_id=patient.id,
                                               pathology_codes=["fabry"]))
            requests.emitir_presupuesto(study["id"], AuthenticatedUser(admin_id, "", UserRole.LAB_ADMINISTRATOR))
            asyncio.run(payments.elegir_modalidad(study["id"], patient_user, "particular"))
            asyncio.run(payments.pagar(study["id"], patient_user))
            day = _book_next_day(booking, patient.usuario_id, study["id"], center_id, day, now)
    print(f"Turnos DEMO: {missing} estudios pagados con turno reservado para la paciente {DEMO_PATIENT_DNI}.")
    return missing


def _first_user(session, role: UserRole) -> int | None:
    return session.scalar(select(Usuario.id).where(Usuario.role == role).order_by(Usuario.id))


def _book_next_day(booking: AppointmentService, user_id, study_id, center_id, after, now):
    """Reserva a las 10 en el primer día hábil libre después de `after`; las reglas son las de la app."""
    for offset in range(1, MAX_DAYS_AHEAD + 1):
        day = after + timedelta(days=offset)
        try:
            booking.reservar(user_id, study_id, center_id, datetime.combine(day, DEMO_SLOT_TIME, TIMEZONE), now)
            return day
        except InvalidSlot:  # fin de semana o feriado
            continue
        except AppointmentConflict:
            if not booking.studies.estudio_habilitado(study_id):
                raise
            # horario tomado en ese centro: se prueba el día siguiente
    raise RuntimeError(f"Turnos DEMO: no hubo horario libre en {MAX_DAYS_AHEAD} días para el estudio {study_id}.")


if __name__ == "__main__":
    seed_demo_extraction_centers()
    seed_demo_booked_studies()
