class StudyRequestConflictError(RuntimeError):
    """La operación no es válida para el estado actual del estudio (HTTP 409).

    El resto de los errores usa los tipos estándar: LookupError (404),
    PermissionError (403) y ValueError (422).
    """
