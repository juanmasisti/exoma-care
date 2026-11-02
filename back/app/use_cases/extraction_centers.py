from datetime import date, datetime

from app.domain.entities.logistics import available_slots, is_business_day
from app.domain.interfaces.extraction_center_repository import ExtractionCenterRepository


class ExtractionCenterService:
    def __init__(self, centers: ExtractionCenterRepository):
        self.centers = centers

    def slots(self, center_id: int, day: date, now: datetime) -> dict:
        if self.centers.get_active_center(center_id) is None:
            raise LookupError("El centro de extracción no existe o no está activo.")
        # Los feriados salen solo de la tabla; los no cargados no se bloquean (decisión 005).
        holiday = self.centers.holiday(day)
        holidays = {day} if holiday is not None else set()
        return {"center_id": center_id, "date": day, "business_day": is_business_day(day, holidays),
                "holiday": holiday, "slots": available_slots(day, holidays, now)}
