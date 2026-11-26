"""Versioned clinical criteria. No network requests or historical-data rewrites."""
import json
import re
import unicodedata
from pathlib import Path
from sqlalchemy import select
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel
from app.infrastructure.database.session import SessionLocal

def normalized(name):
    return unicodedata.normalize("NFKC", name).casefold()

def load_catalog(path=None):
    data = json.loads(Path(path or Path(__file__).with_name("clinical_pathologies.json")).read_text(encoding="utf8"))
    entries = data["pathologies"]
    for field in ("key", "name", "apigen_code", "cdss_code"):
        values = [normalized(e[field]) for e in entries]
        if len(set(values)) != len(values):
            raise ValueError(f"Identidad duplicada: {field}")
    labels = {}
    for e in entries:
        if not e["cardinal"]:
            raise ValueError(f"Falta seleccionar un cardinal para {e['name']}. No se modificó el catálogo.")
        if e["cardinal"] not in e["cardinal_candidates"]:
            raise ValueError("El cardinal no pertenece a la fuente registrada.")
        if any(t not in e["cardinal_candidates"] for t in e.get("additional_cardinals", [])):
            raise ValueError("Cardinal adicional ajeno a la fuente.")
        terms = [e["cardinal"], *e.get("additional_cardinals", []), *e["secondary"]]
        codes = [t["code"] for t in terms]
        if len(set(codes)) != len(codes):
            raise ValueError("Criterios duplicados o superpuestos.")
        if {s["code"] for s in e["secondary"]} & {t["code"] for t in e["cardinal_candidates"]}:
            raise ValueError("Un cardinal externo no puede convertirse en secundario.")
        for t in terms:
            if not re.fullmatch(r"[0-9]{6,18}", t["code"]) or not t["label"].strip():
                raise ValueError("Concepto SNOMED inválido.")
            if t["code"] in labels and labels[t["code"]] != t["label"]:
                raise ValueError("Etiquetas inconsistentes para un concepto.")
            labels[t["code"]] = t["label"]
    return entries

def signature(p):
    term = lambda s: (s.code_system, s.code, s.label)
    return frozenset(term(s) for s in [p.cardinal_symptom, *p.additional_cardinal_symptoms]), {term(s) for s in p.secondary_symptoms}

def expected(entry, system):
    term = lambda s: (system, s["code"], s["label"])
    return frozenset(term(s) for s in [entry["cardinal"], *entry.get("additional_cardinals", [])]), {term(s) for s in entry["secondary"]}

def apply_entry(session, p, entry):
    terms = []
    for t in [entry["cardinal"], *entry.get("additional_cardinals", []), *entry["secondary"]]:
        concept = session.scalar(select(SymptomModel).where(SymptomModel.code_system == "SNOMED", SymptomModel.code == t["code"]))
        if concept is None:
            concept = SymptomModel(code_system="SNOMED", **t)
            session.add(concept)
            session.flush()
        terms.append(concept)
    n = 1 + len(entry.get("additional_cardinals", []))
    p.cardinal_symptom, p.additional_cardinal_symptoms, p.secondary_symptoms = terms[0], terms[1:n], terms[n:]
    p.apigen_code, p.apigen_group, p.cdss_code = entry["apigen_code"], "", entry["cdss_code"]
    session.add(p)

def prepare_catalog(session_factory=SessionLocal, *, apply=False, upgrade=False, entries=None):
    entries = load_catalog() if entries is None else entries
    legacy = {e["key"]: e for e in json.loads(Path(__file__).with_name("demo_pathologies.json").read_text(encoding="utf8"))["pathologies"]}
    report = []
    with session_factory.begin() as session:
        existing = list(session.scalars(select(PathologyModel)))
        for e in entries:
            p = next((p for p in existing if p.normalized_name == normalized(e["name"])), None)
            conflict = any(other is not p and (other.cdss_code == e["cdss_code"] or (other.apigen_code == e["apigen_code"] and other.apigen_group == "")) for other in existing)
            if conflict:
                status = "conflicto_identidad"
            elif p is None:
                status = "crear"
            elif (p.apigen_code, p.apigen_group, p.cdss_code) not in ((None,None,None),(e["apigen_code"],"",e["cdss_code"])):
                status = "conservar_personalizada"
            elif signature(p) == expected(e, "SNOMED"):
                status = "sin_cambios"
            elif upgrade and p.name == legacy[e["key"]]["name"] and signature(p) == expected(legacy[e["key"]], "DEMO"):
                status = "actualizar_demo"
            else:
                status = "conservar_personalizada"
            report.append({"name": e["name"], "action": status})
            if apply and status in ("crear", "actualizar_demo"):
                if p is None:
                    p = PathologyModel(name=e["name"], normalized_name=normalized(e["name"]))
                    existing.append(p)
                apply_entry(session,p,e)
        if not apply:
            session.rollback()
    return report

def seed():
    result = prepare_catalog(apply=True)
    print("Catálogo clínico:", result)
    return sum(r["action"] == "crear" for r in result)
