"""Provincias reales con centros de extracción ficticios (DEMO), feriados fijos, turnos y muestras DEMO."""
import asyncio
from datetime import datetime, time, timedelta
from decimal import Decimal
import json
from pathlib import Path

from sqlalchemy import func, select

from app.domain.entities.logistics import TIMEZONE, SampleStatus, fixed_national_holidays, study_code
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.database.logistics_models import (
    ExtractionCenterModel,
    ExtractionNoticeModel,
    HolidayModel,
    ProvinceModel,
)
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import (
    SQLAlchemyExtractionCenterRepository,
)
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.infrastructure.repositories.sqlalchemy_sample_set_repository import SQLAlchemySampleSetRepository
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.infrastructure.repositories.sqlalchemy_study_request_repository import SqlAlchemyStudyRequestRepository
from app.use_cases.appointments import AppointmentConflict, AppointmentService, InvalidSlot
from app.use_cases.extraction import ExtractionService
from app.use_cases.studies import StudyService
from app.use_cases.study_payments import StudyPaymentService
from app.use_cases.study_requests import StudyRequestService

CENTER_OFFSET_DEGREES = 0.002


DEMO_PATIENT_DNI = "45000001"
DEMO_BOOKED_STUDIES = 3
DEMO_SLOT_TIME = time(10, 0)
MAX_DAYS_AHEAD = 60

DEMO_SAMPLES_DAYS_AGO = 60
DEMO_SAMPLE_VOLUME_ML = Decimal("4")
# Los pasos de una muestra desde que está lista para retirar, en orden.
SAMPLE_PATH = (SampleStatus.READY_FOR_PICKUP, SampleStatus.WITH_TRANSPORTER, SampleStatus.RECEIVED,
               SampleStatus.IN_SAMPLE_SET)
# Muestras DEMO para probar T04, T05 y T06 por separado: grupo -> (centros, último estado, lote).
# Cada centro es un centro DEMO por ciudad y número; los de La Plata son de Buenos Aires.
DEMO_SAMPLE_GROUPS = {
    "lista": ([("La Plata", 1), ("La Plata", 1), ("La Plata", 2), ("La Plata", 3), ("Córdoba", 1)],
              SampleStatus.READY_FOR_PICKUP, None),
    "recibida": ([("La Plata", 1)] * 2, SampleStatus.RECEIVED, None),
    "lote-cerrado": ([("La Plata", 1)] * 10, SampleStatus.IN_SAMPLE_SET, "closed"),
    "lote-armando": ([("La Plata", 1)] * 9, SampleStatus.IN_SAMPLE_SET, "assembling"),
}


def seed() -> tuple[tuple[int, int, int], int, int]:
    return seed_demo_extraction_centers(), seed_demo_booked_studies(), seed_demo_logistics_samples()


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
        requests, payments = _study_flow(session)
        booking = AppointmentService(appointments, SQLAlchemyExtractionCenterRepository(session),
                                     StudyService(SQLAlchemyStudyRepository(session)))
        day = now.date()
        for _ in range(missing):
            study_id = _paid_study(requests, payments, patient, physician_id, admin_id)
            day = _book_next_day(booking, patient.usuario_id, study_id, center_id, day, now)
    print(f"Turnos DEMO: {missing} estudios pagados con turno reservado para la paciente {DEMO_PATIENT_DNI}.")
    return missing


def seed_demo_logistics_samples(session_factory=SessionLocal, now=None) -> int:
    """Deja muestras DEMO de la paciente DEMO en cada estado de logística (DEMO_SAMPLE_GROUPS).

    Cada muestra pasa por el flujo real: estudio pagado, turno pasado, aviso de extracción con 4 ml
    y el recorrido con `change_status`. Un grupo ya cargado (por el id de sus avisos) no se repite,
    aunque sus muestras hayan avanzado después. No guarda recorridos ni retiros: eso lo arma T04.
    """
    now = now or datetime.now(TIMEZONE)
    with session_factory() as session:
        patient = session.scalar(select(Paciente).where(Paciente.dni == DEMO_PATIENT_DNI))
        physician_id = patient.created_by_physician_id if patient else None
        physician_id = physician_id or _first_user(session, UserRole.TREATING_PHYSICIAN)
        admin_id = _first_user(session, UserRole.LAB_ADMINISTRATOR)
        names = {f"Centro de extracción DEMO {city} {number}"
                 for centers, _, _ in DEMO_SAMPLE_GROUPS.values() for city, number in centers}
        center_ids = dict(session.execute(select(ExtractionCenterModel.name, ExtractionCenterModel.id)
                                          .where(ExtractionCenterModel.name.in_(names))).all())
        if patient is None or patient.usuario_id is None or None in (physician_id, admin_id) \
                or len(center_ids) < len(names):
            print("Muestras DEMO: falta la paciente DEMO con usuario, un médico, un administrativo o los centros "
                  "DEMO; no se creó nada.")
            return 0
        requests, payments = _study_flow(session)
        studies = StudyService(SQLAlchemyStudyRepository(session))
        appointments = SQLAlchemyAppointmentRepository(session)
        booking = AppointmentService(appointments, SQLAlchemyExtractionCenterRepository(session), studies)
        samples = SQLAlchemySampleRepository(session)
        extraction = ExtractionService(samples, appointments, studies, _NoResampleNotice())
        sample_sets = SQLAlchemySampleSetRepository(session)
        day = now.date() - timedelta(days=DEMO_SAMPLES_DAYS_AGO)
        created = 0
        for group, (centers, last_status, sample_set_status) in DEMO_SAMPLE_GROUPS.items():
            loaded = session.scalar(select(func.count(ExtractionNoticeModel.id))
                                    .where(ExtractionNoticeModel.external_id.like(f"seed-logistica-{group}-%")))
            if loaded == len(centers):
                print(f"Muestras DEMO: el grupo {group} ya está cargado.")
                continue
            if loaded:
                # Cada aviso se confirma solo: una corrida cortada deja el grupo a medias y no se adivina el resto.
                print(f"Muestras DEMO: el grupo {group} quedó incompleto ({loaded} de {len(centers)}); "
                      "revisalo o empezá con una base nueva.")
                continue
            # Solo puede haber un lote armándose: si ya hay uno (de la demo), no se arma otro.
            if sample_set_status and sample_sets.assembling() is not None:
                print(f"Muestras DEMO: ya hay un lote armándose; no se cargó el grupo {group}.")
                continue
            sample_ids = []
            for number, (city, center_number) in enumerate(centers, start=1):
                study_id = _paid_study(requests, payments, patient, physician_id, admin_id)
                center_id = center_ids[f"Centro de extracción DEMO {city} {center_number}"]
                # Turno en el pasado: se reserva con un "ahora" anterior, con las mismas reglas de la app.
                day = _book_next_day(booking, patient.usuario_id, study_id, center_id, day,
                                     datetime.combine(day, time(0), TIMEZONE))
                taken_at = datetime.combine(day, DEMO_SLOT_TIME, TIMEZONE)
                result, _ = extraction.registrar_aviso(f"seed-logistica-{group}-{number}", study_code(study_id),
                                                       DEMO_SAMPLE_VOLUME_ML, taken_at, taken_at)
                sample_ids.append(result["sample_id"])
            moved_at = _move(samples, sample_ids, last_status, taken_at, admin_id)
            if sample_set_status:
                sample_set_id = sample_sets.open_set(False, moved_at)
                for slot, sample_id in enumerate(sample_ids, start=1):
                    sample_sets.add_item(sample_set_id, sample_id, slot)
                if sample_set_status == "closed":
                    # Sin autorización del Ministerio: el enganche del cierre lo arma T06.
                    sample_sets.close(sample_set_id, moved_at)
            session.commit()
            created += len(sample_ids)
            print(f"Muestras DEMO: {len(sample_ids)} en el grupo {group} ({last_status.value}).")
    return created


def _move(samples: SQLAlchemySampleRepository, sample_ids, last_status, at, actor_id) -> datetime:
    """Hasta `last_status`, una hora por paso; devuelve la hora del último. Lo firma la administrativa:
    todavía no hay rol transportista."""
    steps = SAMPLE_PATH[:SAMPLE_PATH.index(last_status) + 1]
    for current, new in zip(steps, steps[1:]):
        at += timedelta(hours=1)
        samples.change_status(sample_ids, current.value, new.value, at, actor_id)
    return at


class _NoResampleNotice:
    """Las muestras DEMO tienen 4 ml: nunca hay que avisar un remuestreo."""

    def avisar_remuestreo(self, study_id: int, sample_id: int, motivo: str) -> None:
        raise RuntimeError("Muestras DEMO: no debería pedirse un remuestreo.")


def _study_flow(session):
    studies = SqlAlchemyStudyRequestRepository(session)
    # Particular y sin cupón: no se consultan obras sociales ni cupones.
    return StudyRequestService(studies, DemoGeneCatalog()), StudyPaymentService(studies, insurance=None, coupons=None)


def _paid_study(requests: StudyRequestService, payments: StudyPaymentService, patient, physician_id, admin_id) -> int:
    """Estudio de Fabry pagado por el flujo de estudios (solicitud, presupuesto y pago particular simulado)."""
    patient_user = AuthenticatedUser(patient.usuario_id, "", UserRole.PATIENT)
    study = asyncio.run(requests.crear(physician_id=physician_id, patient_id=patient.id, pathology_codes=["fabry"]))
    requests.emitir_presupuesto(study["id"], AuthenticatedUser(admin_id, "", UserRole.LAB_ADMINISTRATOR))
    asyncio.run(payments.elegir_modalidad(study["id"], patient_user, "particular"))
    asyncio.run(payments.pagar(study["id"], patient_user))
    return study["id"]


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
    seed()
