"""Mails del circuito de estudios (EC-13/EC-14) con el servicio común de avisos, sin red."""

import asyncio
from datetime import UTC, datetime

from study_request_fakes import InMemoryStudyRequestRepository

from app.domain.dtos.notification_dto import NotificacionResultado
from app.domain.entities.study import StudyStatus
from app.domain.entities.study_request import GeneRef, StudyRequest
from app.infrastructure.email_study_notifier import EmailStudyNotifier

AVISO_ID = "00000000-0000-4000-8000-000000000001"


class FakeAvisos:
    def __init__(self, fail_on: str | None = None):
        self.sent = []
        self.fail_on = fail_on

    async def execute(self, datos):
        self.sent.append(datos)
        if self.fail_on and self.fail_on in datos.idempotency_key:
            raise RuntimeError("API de avisos caída")
        return NotificacionResultado(aviso_id=AVISO_ID, estado="pendiente", creado=True)


def repo():
    repo = InMemoryStudyRequestRepository()
    repo.add_physician(10)
    repo.add_patient(1, "Paciente Demo", 40, email="paciente@example.test")
    repo.add_user(20, "lab_administrator", "admin1@example.test")
    repo.add_user(21, "lab_administrator", "admin2@example.test")
    repo.add_user(50, "bioinformatician", "bio@example.test")
    return repo


def study(status, original_study_id=None):
    return StudyRequest(
        id=7, patient_id=1, physician_id=10, status=status, include_secondary_findings=False,
        created_at=datetime.now(UTC), pathologies=(), genes=(GeneRef("GLA", "manual"),),
        original_study_id=original_study_id,
    )


def by_key(avisos):
    return {datos.idempotency_key: datos for datos in avisos.sent}


def test_reanalysis_request_mails_patient_and_administration():
    avisos = FakeAvisos()
    notifier = EmailStudyNotifier(repo(), lambda: avisos)
    asyncio.run(notifier.reanalisis_solicitado(study(StudyStatus.CREATED, original_study_id=3)))
    sent = by_key(avisos)
    assert sent["reanalisis-7-solicitado-paciente"].destinatarios == ["paciente@example.test"]
    assert sent["reanalisis-7-solicitado-administracion"].destinatarios == [
        "admin1@example.test", "admin2@example.test",
    ]
    assert "EST-000003" in sent["reanalisis-7-solicitado-paciente"].asunto
    assert sent["reanalisis-7-solicitado-paciente"].referencia == "7"


def test_paid_study_mails_patient_and_physician():
    avisos = FakeAvisos()
    asyncio.run(EmailStudyNotifier(repo(), lambda: avisos).estudio_habilitado(study(StudyStatus.PAID)))
    sent = by_key(avisos)
    assert set(sent) == {"estudio-7-habilitado-paciente", "estudio-7-habilitado-medico"}
    assert sent["estudio-7-habilitado-medico"].destinatarios == ["u10@demo.test"]
    assert "turno" in sent["estudio-7-habilitado-paciente"].mensaje


def test_paid_reanalysis_mails_patient_and_physician_only():
    avisos = FakeAvisos()
    notifier = EmailStudyNotifier(repo(), lambda: avisos)
    asyncio.run(notifier.estudio_habilitado(study(StudyStatus.IN_BIOINFORMATICS, original_study_id=3)))
    sent = by_key(avisos)
    assert set(sent) == {"estudio-7-habilitado-paciente", "estudio-7-habilitado-medico"}
    assert "no hace falta una nueva extracción" in sent["estudio-7-habilitado-paciente"].mensaje


def test_a_failing_mail_does_not_stop_the_others_nor_raise():
    avisos = FakeAvisos(fail_on="paciente")
    notifier = EmailStudyNotifier(repo(), lambda: avisos)
    asyncio.run(notifier.estudio_habilitado(study(StudyStatus.PAID)))
    assert [d.idempotency_key for d in avisos.sent] == [
        "estudio-7-habilitado-paciente", "estudio-7-habilitado-medico",
    ]


def test_missing_avisos_configuration_is_logged_not_raised():
    def unconfigured():
        raise RuntimeError("Configura NOTIFICATIONS_API_KEY")

    asyncio.run(EmailStudyNotifier(repo(), unconfigured).estudio_habilitado(study(StudyStatus.PAID)))
