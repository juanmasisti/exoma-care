from fastapi import FastAPI

from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.auth import router as auth_router
from app.api.routes.bioinformatics import router as bioinformatics_router
from app.api.routes.extraction_centers import router as extraction_center_router
from app.api.routes.family import router as family_router
from app.api.routes.pathologies import router as pathology_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.patients import router as patient_router
from app.api.routes.studies import router as study_router

app = FastAPI(title="EXOMA CARE API")
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(pathology_router)
app.include_router(patient_router)
app.include_router(family_router)
app.include_router(extraction_center_router)
app.include_router(study_router)
app.include_router(bioinformatics_router)
app.include_router(notifications_router)
