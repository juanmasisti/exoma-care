import unicodedata

from sqlalchemy import func, select
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
    )


class SQLAlchemyPathologyRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _query():
        return select(PathologyModel).options(
            selectinload(PathologyModel.cardinal_symptom),
            selectinload(PathologyModel.secondary_symptoms),
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

    def symptom_ids_exist(self, ids: set[int]) -> bool:
        if not ids:
            return True
        found = set(self.session.scalars(select(SymptomModel.id).where(SymptomModel.id.in_(ids))))
        return found == ids

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
