import unicodedata

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.entities.pathology import PathologyDefinition
from app.domain.interfaces.pathology_repository import (
    DuplicatePathologyName, Pathology, Symptom,
)
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel


def symptom_record(model: SymptomModel) -> Symptom:
    return Symptom(model.id, model.code, model.label, model.code_system)


def pathology_record(model: PathologyModel) -> Pathology:
    return Pathology(
        model.id, model.name, symptom_record(model.cardinal_symptom),
        tuple(symptom_record(s) for s in model.secondary_symptoms),
        model.apigen_code, model.apigen_group, model.cdss_code,
        tuple(symptom_record(s) for s in model.additional_cardinal_symptoms),
    )


class SQLAlchemyPathologyRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _query():
        return select(PathologyModel).options(
            selectinload(PathologyModel.cardinal_symptom),
            selectinload(PathologyModel.secondary_symptoms),
            selectinload(PathologyModel.additional_cardinal_symptoms),
        )

    def list_pathologies(self) -> list[Pathology]:
        models = self.session.scalars(self._query().order_by(PathologyModel.name)).all()
        return [pathology_record(m) for m in models]

    def get_pathology(self, pathology_id: int) -> Pathology | None:
        model = self.session.scalar(self._query().where(PathologyModel.id == pathology_id))
        return pathology_record(model) if model else None

    def list_symptoms(self, query: str) -> list[Symptom]:
        query = query.strip().lower()
        statement = select(SymptomModel)
        if query:
            # contains con autoescape trata % y _ como texto, no como comodines.
            statement = statement.where(
                func.lower(SymptomModel.label).contains(query, autoescape=True)
                | func.lower(SymptomModel.code).contains(query, autoescape=True)
            )
        return [symptom_record(s) for s in self.session.scalars(
            statement.order_by(SymptomModel.label).limit(100)
        )]

    def get_symptoms(self, ids: set[int]) -> list[Symptom]:
        return [symptom_record(s) for s in self.session.scalars(
            select(SymptomModel).where(SymptomModel.id.in_(ids)).order_by(SymptomModel.id))]

    def symptom_ids_exist(self, ids: set[int]) -> bool:
        if not ids:
            return True
        found = set(self.session.scalars(select(SymptomModel.id).where(SymptomModel.id.in_(ids))))
        return found == ids

    def link_external(self, pathology_id: int, apigen_code: str, apigen_group: str, cdss_code: str | None) -> Pathology:
        model = self.session.get(PathologyModel, pathology_id)
        if model is None:
            raise LookupError("La patología no existe.")
        if model.apigen_code is not None and (model.apigen_code, model.apigen_group, model.cdss_code) != (apigen_code, apigen_group, cdss_code):
            raise ValueError("La identidad externa ya está asociada y no puede reemplazarse.")
        try:
            changed = self.session.execute(update(PathologyModel).where(
                PathologyModel.id == pathology_id, PathologyModel.apigen_code.is_(None)
            ).values(apigen_code=apigen_code, apigen_group=apigen_group, cdss_code=cdss_code))
            if changed.rowcount == 0:
                self.session.expire_all()
                current = self.session.get(PathologyModel, pathology_id)
                if current is None or (current.apigen_code, current.apigen_group, current.cdss_code) != (apigen_code, apigen_group, cdss_code):
                    self.session.rollback()
                    raise ValueError("La identidad fue asociada por otra operación. Actualizá el catálogo.")
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise ValueError("La identidad externa ya está asociada a otra patología local.") from None
        self.session.expire_all()
        return self.get_pathology(pathology_id)

    def save(self, definition: PathologyDefinition, pathology_id: int | None) -> Pathology:
        normalized = unicodedata.normalize("NFKC", definition.name).casefold()
        duplicate = self.session.scalar(select(PathologyModel.id).where(
            PathologyModel.normalized_name == normalized
        ))
        if duplicate is not None and duplicate != pathology_id:
            raise DuplicatePathologyName("Ya existe una patología con ese nombre.")
        model = self.session.get(PathologyModel, pathology_id) if pathology_id else PathologyModel()
        if model is None:
            raise LookupError("La patología no existe.")
        model.name = definition.name
        model.normalized_name = normalized
        model.cardinal_symptom_id = definition.cardinal_symptom_id
        model.additional_cardinal_symptoms = list(self.session.scalars(select(SymptomModel).where(
            SymptomModel.id.in_(definition.additional_cardinal_ids - {definition.cardinal_symptom_id})
        ).order_by(SymptomModel.id)))
        model.secondary_symptoms = list(self.session.scalars(select(SymptomModel).where(
            SymptomModel.id.in_(definition.secondary_symptom_ids)
        ).order_by(SymptomModel.id)))
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            # La restricción única también cubre altas simultáneas.
            if self.session.scalar(select(PathologyModel.id).where(
                PathologyModel.normalized_name == normalized
            )) is not None:
                raise DuplicatePathologyName("Ya existe una patología con ese nombre.") from None
            raise
        self.session.expire_all()
        return self.get_pathology(model.id)
