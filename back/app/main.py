from fastapi import FastAPI

from app.api.routes.auth import router as auth_router

from app.api.routes.pathologies import router as pathology_router

app = FastAPI(title="EXOMA CARE API")
app.include_router(auth_router)

app.include_router(pathology_router)
