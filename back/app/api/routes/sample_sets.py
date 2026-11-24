from fastapi import APIRouter

# Vacío en la base (decisión 016): T05 agrega GET /api/sample-sets y GET /api/sample-sets/{id}.
router = APIRouter(prefix="/api/sample-sets", tags=["sample sets"])
