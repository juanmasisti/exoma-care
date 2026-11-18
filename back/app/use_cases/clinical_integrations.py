"""External orientation never participates in local suspicion validation."""
import re
from app.config import get_settings

class ClinicalIntegrations:
    def __init__(self, catalog, apigen=None, cdss=None):
        self.catalog, self.apigen, self.cdss = catalog, apigen, cdss

    async def link(self, pathology_id, apigen_code, de_grupo, cdss_code):
        self.catalog.get(pathology_id)
        group = get_settings().apigen_group_id
        items = await self.apigen.listar_patologias_grupo(group)
        if not any(item["codigo"] == apigen_code and item["de_grupo"] == de_grupo for item in items):
            raise ValueError("La identidad seleccionada no existe en el catálogo de Apigen.")
        if cdss_code is not None:
            clinical = await self.cdss.obtener_catalogo_completo()
            if not any(item["codigo"] == cdss_code for item in clinical):
                raise ValueError("La identidad seleccionada no existe en CDSS.")
        return self.catalog.repository.link_external(pathology_id, apigen_code, group if de_grupo else "", cdss_code)

    async def advise(self, symptom_ids):
        self.catalog._require_symptoms(set(symptom_ids))
        symptoms = self.catalog.repository.get_symptoms(set(symptom_ids))
        included = [s for s in symptoms if s.code_system == "SNOMED" and re.fullmatch(r"[0-9]{6,18}", s.code)]
        if not included:
            raise ValueError("Seleccioná al menos un síntoma SNOMED. Los conceptos DEMO no se envían a CDSS.")
        result = await self.cdss.sugerir(list(dict.fromkeys(s.code for s in included)))
        return {"result": result, "sent_symptom_ids": [s.id for s in included], "excluded_symptom_ids": [s.id for s in symptoms if s not in included]}
