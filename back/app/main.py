from fastapi import FastAPI

from app.api.routes.auth import router as auth_router

from app.api.routes.pathologies import router as pathology_router

from app.api.routes.patients import router as patient_router

from app.api.routes.extraction_centers import router as extraction_center_router

app = FastAPI(title="EXOMA CARE API")
app.include_router(auth_router)

app.include_router(pathology_router)

app.include_router(patient_router)

app.include_router(extraction_center_router)
