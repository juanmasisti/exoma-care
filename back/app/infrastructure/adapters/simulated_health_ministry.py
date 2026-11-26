"""SIMULADO: ningún grupo tiene el módulo del Ministerio de Salud (decisión 012).

Recibe el mismo CSV que recibiría el servicio real y siempre autoriza, con un PDF armado
a partir de esas filas. Solo el caso de éxito.
"""
from fpdf import FPDF

from app.domain.interfaces.health_ministry import MinistryAuthorization


class SimulatedHealthMinistry:
    def solicitar_autorizacion(self, csv: str) -> MinistryAuthorization:
        pdf = FPDF(format="A4")
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Autorización del Ministerio de Salud (SIMULADA)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        for row in csv.splitlines():
            if row.strip():
                # Helvetica solo dibuja latin-1: un carácter fuera de rango sale como "?" y no rompe el PDF.
                pdf.multi_cell(0, 6, row.encode("latin-1", "replace").decode("latin-1"), new_x="LMARGIN", new_y="NEXT")
        return MinistryAuthorization(status="autorizado", pdf=bytes(pdf.output()))
