"""PROVISORIO: estados mínimos del estudio para destrabar turnos; lo amplía el área de estudios (Tomás).

Nombres tomados del glosario. Sin transiciones: las define Tomás.
"""

STUDY_STATUSES = (
    "creado",
    "pendiente_pago",
    "pendiente_autorizacion",
    "pagado",
    "autorizado",
    "rechazado",
    "turno_sacado",
    "listo_para_retirar",
    "requiere_remuestreo",
    "en_viaje_a_corea",
    "en_area_bioinformatica",
    "en_analisis",
    "resultado_disponible",
)

# Estados que permiten sacar turno de extracción.
ENABLED_STUDY_STATUSES = frozenset({"pagado", "autorizado"})
