"""Armado automático de sample sets (EC-17) y Pompe urgente (EC-19)."""
from __future__ import annotations

from datetime import UTC, date, datetime

from app.domain.entities.logistics import TIMEZONE, SampleStatus, is_urgent_pompe, sample_set_must_close
from app.domain.interfaces.sample_repository import SampleRepository
from app.domain.interfaces.sample_set_hooks import SampleSetClosedHandler
from app.domain.interfaces.sample_set_repository import (
    AssemblingSetExists, SampleSetRepository, SetFull, SetNotAssembling, SlotTaken,
)

# Choques seguidos (lote abierto o cerrado por otro pedido) antes de rendirse y deshacer la llegada.
MAX_ATTEMPTS = 5


def pompe_reference_date(study_created_at: datetime) -> date:
    """Fecha en la que se mide si el paciente es menor de 4 meses: el alta del estudio.

    Decisión abierta 5 del dominio: propuesta pendiente de confirmar con el profesor (decisión 018).
    Si elige otra fecha (extracción o cierre del lote), se cambia solo acá.
    """
    # SQLite devuelve la fecha sin zona: se guardó en UTC.
    if study_created_at.tzinfo is None:
        study_created_at = study_created_at.replace(tzinfo=UTC)
    return study_created_at.astimezone(TIMEZONE).date()


class SampleSetService:
    def __init__(self, sample_sets: SampleSetRepository, samples: SampleRepository,
                 closed_handler: SampleSetClosedHandler):
        self.sample_sets = sample_sets
        self.samples = samples
        self.closed_handler = closed_handler

    def es_pompe_urgente(self, study_id: int) -> bool:
        """Para bioinformática (Camila): mostrar primero los Pompe urgentes."""
        inputs = self.sample_sets.pompe_inputs(study_id)
        if inputs is None:
            raise LookupError("El estudio no existe.")
        # ABIERTO (decisión 018): sin fecha de nacimiento no se puede saber la edad; se propone "no es urgente".
        if inputs["birth_date"] is None:
            return False
        return is_urgent_pompe(inputs["pathology_codes"], inputs["birth_date"],
                               pompe_reference_date(inputs["study_created_at"]))

    def asignar_a_sample_set(self, sample_id: int, now: datetime) -> None:
        """Lo llama la llegada por cada muestra recibida. Sin commit ni rollback: los hace la llegada."""
        if now.tzinfo is None:
            raise ValueError("La hora actual debe indicar la zona horaria.")
        study_id = self.sample_sets.study_for_sample(sample_id)
        if study_id is None:
            raise LookupError("La muestra no existe.")
        changed = self.samples.change_status([sample_id], SampleStatus.RECEIVED.value,
                                             SampleStatus.IN_SAMPLE_SET.value, now)
        if changed == 0:
            raise ValueError("La muestra no está recibida: no se puede sumar a un lote.")
        urgent = self.es_pompe_urgente(study_id)
        sample_set_id = self._add_to_assembling_set(sample_id, urgent, now)
        count = len(self.sample_sets.get(sample_set_id)["items"])
        # Solo quien gana el cierre avisa: si otro pedido ya lo cerró, `close` devuelve False.
        if sample_set_must_close(count, urgent) and self.sample_sets.close(sample_set_id, now, is_urgent=urgent):
            self.closed_handler.al_cerrar_lote(sample_set_id, now)

    def _add_to_assembling_set(self, sample_id: int, urgent: bool, now: datetime) -> int:
        # Sin FOR UPDATE (SQLite no lo respeta): cada choque lo rechaza una restricción de la base y se reintenta.
        for _ in range(MAX_ATTEMPTS):
            sample_set = self.sample_sets.assembling()
            if sample_set is None:
                try:
                    sample_set = {"id": self.sample_sets.open_set(urgent, now), "items": []}
                except AssemblingSetExists:
                    continue  # otro pedido abrió uno a la vez: se usa ese
            slot = max((item["slot"] for item in sample_set["items"]), default=0) + 1
            while True:
                try:
                    self.sample_sets.add_item(sample_set["id"], sample_id, slot)
                    return sample_set["id"]
                except SlotTaken:
                    slot += 1  # pasado el 10 da SetFull
                except (SetFull, SetNotAssembling):
                    break  # se llenó o lo cerró otro pedido: releer y, si hace falta, abrir otro
        raise RuntimeError("No se pudo sumar la muestra a un lote: demasiados choques seguidos.")

    def list_sample_sets(self, status: str | None) -> list[dict]:
        return self.sample_sets.list_by_status(status)

    def sample_set(self, sample_set_id: int) -> dict:
        sample_set = self.sample_sets.get(sample_set_id)
        if sample_set is None:
            raise LookupError("El lote no existe.")
        return sample_set
