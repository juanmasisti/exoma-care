from sqlalchemy.orm import Session

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
