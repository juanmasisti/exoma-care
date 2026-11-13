"""PDF de la orden de extracción y del consentimiento informado de un turno (decisión 010)."""
from fpdf import FPDF

# Cada bloque de texto termina en el margen izquierdo de la línea siguiente.
NEXT_LINE = {"new_x": "LMARGIN", "new_y": "NEXT"}


def _printable(text: str) -> str:
    # Helvetica solo dibuja latin-1: un carácter fuera de rango en un dato cargado sale como "?" y no rompe el PDF.
    return text.encode("latin-1", "replace").decode("latin-1")


def _document(title: str) -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, title, **NEXT_LINE)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    return pdf


def _line(pdf: FPDF, label: str, value: str) -> None:
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(45, 8, label)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 8, _printable(value), **NEXT_LINE)


def _patient_name(appointment: dict) -> str:
    patient = appointment["patient"]
    return f"{patient['first_name']} {patient['last_name']}"


def extraction_order_pdf(appointment: dict) -> bytes:
    # starts_at ya viene en hora argentina desde el repositorio (logistics.TIMEZONE).
    starts_at, center = appointment["starts_at"], appointment["center"]
    pdf = _document("Orden de extracción")
    _line(pdf, "Estudio:", appointment["study_code"])
    _line(pdf, "Fecha:", starts_at.strftime("%d/%m/%Y"))
    _line(pdf, "Hora:", starts_at.strftime("%H:%M"))
    _line(pdf, "Centro:", center["name"])
    _line(pdf, "Dirección:", f"{center['address']}, {center['city']}")
    _line(pdf, "Paciente:", _patient_name(appointment))
    _line(pdf, "DNI:", appointment["patient"]["dni"])
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 8, "No requiere ayuno ni preparación especial.", **NEXT_LINE)
    return bytes(pdf.output())


def consent_pdf(appointment: dict) -> bytes:
    pdf = _document("Consentimiento informado (PROVISORIO)")
    pdf.set_font("Helvetica", "I", 10)
    # ABIERTO (decisión 010): el PO tiene una plantilla; este texto se reemplaza por la suya.
    pdf.multi_cell(0, 6, "Texto provisorio: se reemplaza por la plantilla del laboratorio.", **NEXT_LINE)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 7, _printable(
        f"Yo, {_patient_name(appointment)}, DNI {appointment['patient']['dni']}, autorizo la extracción "
        f"de una muestra de sangre para el estudio de exoma clínico {appointment['study_code']}."
    ), **NEXT_LINE)
    pdf.ln(6)
    pdf.multi_cell(0, 7, "Si el paciente es menor de edad, firma su madre, padre o tutor.", **NEXT_LINE)
    pdf.ln(12)
    for label in ("Firma", "Aclaración", "DNI", "Fecha"):
        pdf.cell(0, 12, f"{label}: ______________________________", **NEXT_LINE)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 10)
    pdf.multi_cell(0, 6, "Se imprime, se firma y se entrega en papel. No se sube al sistema.", **NEXT_LINE)
    return bytes(pdf.output())
