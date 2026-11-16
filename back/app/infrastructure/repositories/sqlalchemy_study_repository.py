from datetime import date
from typing import Any

from sqlalchemy import String, or_, select, update
from sqlalchemy.orm import Session

from app.domain.entities.study import BIOINFORMATICS_STATUSES
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.patient_clinical_models import PatientClinicalRevision
from app.infrastructure.database.study_models import StudyModel


class SQLAlchemyStudyRepository:
    def __init__(self, session: Session):
        self.session = session

    def status(self, study_id: int) -> str | None:
        study = self.session.get(StudyModel, study_id)
        return study.status if study is not None else None

    def set_status(self, study_id: int, status: str) -> bool:
        study = self.session.get(StudyModel, study_id)
        if study is None:
            return False
        study.status = status
        self.session.commit()
        return True

    def claim_analysis(self, study_id: int, analyst_id: int) -> bool:
        result = self.session.execute(
            update(StudyModel)
            .where(
                StudyModel.id == study_id,
                StudyModel.status == "en_area_bioinformatica",
            )
            .values(status="en_analisis", analyst_id=analyst_id)
        )
        self.session.commit()
        return result.rowcount == 1

    def claim_unassigned_analysis(self, study_id: int, analyst_id: int) -> bool:
        result = self.session.execute(
            update(StudyModel)
            .where(
                StudyModel.id == study_id,
                StudyModel.status == "en_analisis",
                StudyModel.analyst_id.is_(None),
            )
            .values(analyst_id=analyst_id)
        )
        self.session.commit()
        return result.rowcount == 1

    def analysis_owner(self, study_id: int) -> int | None:
        study = self.session.get(StudyModel, study_id)
        return study.analyst_id if study is not None else None

    def release_analysis(self, study_id: int, analyst_id: int) -> bool:
        result = self.session.execute(
            update(StudyModel)
            .where(
                StudyModel.id == study_id,
                StudyModel.status == "en_analisis",
                StudyModel.analyst_id == analyst_id,
            )
            .values(status="en_area_bioinformatica", analyst_id=None)
        )
        self.session.commit()
        return result.rowcount == 1

    def complete_analysis(
        self, study_id: int, analyst_id: int, result_data: dict[str, Any]
    ) -> bool:
        result = self.session.execute(
            update(StudyModel)
            .where(
                StudyModel.id == study_id,
                StudyModel.status == "en_analisis",
                StudyModel.analyst_id == analyst_id,
            )
            .values(status="resultado_disponible", result_json=result_data)
        )
        self.session.commit()
        return result.rowcount == 1

    def result_for_analyst(
        self, study_id: int, analyst_id: int
    ) -> dict[str, Any] | None:
        study = self.session.scalar(
            select(StudyModel).where(
                StudyModel.id == study_id,
                StudyModel.status == "resultado_disponible",
                StudyModel.analyst_id == analyst_id,
            )
        )
        return study.result_json if study is not None else None

    def notification_recipients(self, study_id: int) -> list[dict[str, str]]:
        patient = self.session.execute(
            select(Paciente.email, Paciente.usuario_id, Paciente.created_by_physician_id)
            .join(StudyModel, StudyModel.patient_id == Paciente.id)
            .where(StudyModel.id == study_id)
        ).one_or_none()
        if patient is None:
            return []

        patient_email = patient.email
        if patient.usuario_id is not None:
            account_email = self.session.scalar(
                select(Usuario.email).where(Usuario.id == patient.usuario_id)
            )
            patient_email = account_email or patient_email

        if not patient_email:
            return []

        recipients: list[dict[str, str]] = []
        recipients.append({"canal": "email", "destino": patient_email})
        if patient.created_by_physician_id is not None:
            physician_email = self.session.scalar(
                select(Usuario.email).where(
                    Usuario.id == patient.created_by_physician_id
                )
            )
            if physician_email and physician_email != patient_email:
                recipients.append({"canal": "email", "destino": physician_email})
        return recipients

    def physician_owns_study(self, study_id: int, physician_id: int) -> bool:
        return (
            self.session.scalar(
                select(Paciente.id)
                .join(StudyModel, StudyModel.patient_id == Paciente.id)
                .where(
                    StudyModel.id == study_id,
                    Paciente.created_by_physician_id == physician_id,
                )
            )
            is not None
        )

    def list_bioinformatics_studies(self) -> list[dict[str, Any]]:
        studies = self.session.scalars(
            select(StudyModel)
            .join(Paciente, Paciente.id == StudyModel.patient_id)
            .where(StudyModel.status.in_(BIOINFORMATICS_STATUSES))
            .order_by(StudyModel.created_at, StudyModel.id)
        )
        return [self._study_summary(study) for study in studies]

    def bioinformatics_study(self, study_id: int) -> dict[str, Any] | None:
        study = self.session.get(StudyModel, study_id)
        if study is None:
            return None
        return self._study_summary(study)

    def list_study_history(self, query: str = "") -> list[dict[str, Any]]:
        statement = (
            select(StudyModel)
            .join(Paciente, Paciente.id == StudyModel.patient_id)
            .where(StudyModel.status == "resultado_disponible")
        )
        search = query.strip()
        if search:
            statement = statement.where(
                or_(
                    Paciente.nombre.contains(search, autoescape=True),
                    Paciente.apellido.contains(search, autoescape=True),
                    Paciente.dni.contains(search, autoescape=True),
                    StudyModel.id.cast(String).contains(search, autoescape=True),
                )
            )
        studies = self.session.scalars(
            statement.order_by(StudyModel.created_at.desc(), StudyModel.id.desc())
        )
        return [self._study_summary(study) for study in studies]

    def _study_summary(self, study: StudyModel) -> dict[str, Any]:
        patient = self.session.get(Paciente, study.patient_id)
        if patient is None:
            raise RuntimeError(f"El estudio {study.id} referencia un paciente inexistente.")
        revision = self.session.scalar(
            select(PatientClinicalRevision)
            .where(PatientClinicalRevision.patient_id == patient.id)
            .order_by(PatientClinicalRevision.version.desc())
            .limit(1)
        )
        physician = (
            self.session.get(Usuario, patient.created_by_physician_id)
            if patient.created_by_physician_id is not None
            else None
        )
        snapshot = revision.snapshot if revision is not None else {}
        return {
            "id": study.id,
            "patient_id": study.patient_id,
            "patient_name": f"{patient.nombre} {patient.apellido}".strip(),
            "patient_dni": patient.dni,
            "patient": {
                "id": patient.id,
                "nombre": patient.nombre,
                "apellido": patient.apellido,
                "dni": patient.dni,
                "fecha_nacimiento": patient.fecha_nacimiento,
                "telefono": patient.telefono,
                "email": patient.email,
                "clinical_summary": patient.clinical_summary,
                "suspicion_type": patient.suspicion_type,
                "family_history": patient.family_history,
                "created_at": patient.created_at,
                "updated_at": patient.updated_at,
                "clinical_revision": snapshot,
                "physician": (
                    {
                        "id": physician.id,
                        "nombre": physician.first_name,
                        "apellido": physician.last_name,
                        "email": physician.email,
                        "license_number": physician.license_number,
                        "specialty": physician.specialty,
                    }
                    if physician is not None
                    else None
                ),
            },
            "status": study.status,
            "analyst_id": study.analyst_id,
            "created_at": study.created_at,
            "codigo_patologia": study.codigo_patologia,
            "variantes_detectadas": study.variantes_detectadas,
            "resultado_diagnostico": study.resultado_diagnostico,
            "hallazgos_secundarios": study.hallazgos_secundarios,
            "fecha_reevaluacion": study.fecha_reevaluacion,
        }

    def start_analysis(self, study_id: int, analyst_id: int) -> bool:
        return self.claim_analysis(study_id, analyst_id)

    def save_bioinformatics_result(
        self,
        study_id: int,
        analyst_id: int,
        variantes_detectadas: list[dict[str, Any]],
        resultado_diagnostico: str,
        hallazgos_secundarios: list[dict[str, Any]],
        fecha_reevaluacion: date | None,
        codigo_patologia: str,
    ) -> bool:
        result_json = {
            "variantes_detectadas": variantes_detectadas,
            "resultado_diagnostico": resultado_diagnostico,
            "hallazgos_secundarios": hallazgos_secundarios,
            "fecha_reevaluacion": (
                fecha_reevaluacion.isoformat() if fecha_reevaluacion else None
            ),
        }
        result = self.session.execute(
            update(StudyModel)
            .where(
                StudyModel.id == study_id,
                StudyModel.status.in_(BIOINFORMATICS_STATUSES),
                or_(StudyModel.analyst_id.is_(None), StudyModel.analyst_id == analyst_id),
            )
            .values(
                status="resultado_disponible",
                analyst_id=analyst_id,
                variantes_detectadas=variantes_detectadas,
                resultado_diagnostico=resultado_diagnostico,
                hallazgos_secundarios=hallazgos_secundarios,
                fecha_reevaluacion=fecha_reevaluacion,
                codigo_patologia=codigo_patologia,
                result_json=result_json,
            )
        )
        self.session.commit()
        return result.rowcount == 1
