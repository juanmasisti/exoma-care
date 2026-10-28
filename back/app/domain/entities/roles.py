from enum import Enum


class UserRole(str, Enum):
    TREATING_PHYSICIAN = "treating_physician"
    LAB_ADMINISTRATOR = "lab_administrator"
    BIOINFORMATICIAN = "bioinformatician"
    PATIENT = "patient"
    MEDICAL_MANAGER = "medical_manager"

    @property
    def display_name(self) -> str:
        return {
            UserRole.TREATING_PHYSICIAN: "Médico",
            UserRole.LAB_ADMINISTRATOR: "Administrativo",
            UserRole.BIOINFORMATICIAN: "Bioinformático",
            UserRole.PATIENT: "Paciente",
            UserRole.MEDICAL_MANAGER: "Gerente",
        }[self]
