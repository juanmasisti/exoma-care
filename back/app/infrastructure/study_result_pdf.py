from fpdf import FPDF


def _latin1(value: object) -> str:
    return str(value or "").encode("latin-1", "replace").decode("latin-1")


def render_study_result_pdf(study: dict) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "EXOMA CARE - Resultado de estudio", ln=1)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Estudio: {study['id']}", ln=1)
    pdf.cell(0, 8, f"Paciente: {_latin1(study.get('patient_name', 'No disponible'))}", ln=1)
    pdf.cell(0, 8, f"DNI: {_latin1(study.get('patient_dni', 'No disponible'))}", ln=1)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Diagnostico", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, _latin1(study.get("resultado_diagnostico") or "No disponible"))

    if study.get("codigo_patologia"):
        pdf.cell(0, 8, f"Codigo de patologia: {_latin1(study['codigo_patologia'])}", ln=1)

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Variantes detectadas", ln=1)
    pdf.set_font("Helvetica", "", 10)
    variants = study.get("variantes_detectadas") or []
    if not variants:
        pdf.cell(0, 7, "No se registraron variantes.", ln=1)
    for variant in variants:
        fields = (
            variant.get("gen"),
            variant.get("hgvs_c"),
            variant.get("proteina"),
            variant.get("clasificacion"),
        )
        pdf.multi_cell(0, 7, "- " + _latin1(" · ".join(str(v) for v in fields if v)))

    findings = study.get("hallazgos_secundarios") or []
    if findings:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Hallazgos secundarios", ln=1)
        pdf.set_font("Helvetica", "", 10)
        for finding in findings:
            pdf.multi_cell(0, 7, "- " + _latin1(finding))

    if study.get("fecha_reevaluacion"):
        pdf.ln(2)
        pdf.cell(0, 8, f"Fecha de reevaluacion: {_latin1(study['fecha_reevaluacion'])}", ln=1)

    return bytes(pdf.output())
