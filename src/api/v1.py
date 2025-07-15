from fastapi import APIRouter
from src.api.endpoints.models import models_router as models_router
from src.api.endpoints.admin import admin_router
from src.api.endpoints.llm import router as llm_router
from src.api.endpoints.groups import groups_router


router_v1 = APIRouter()
router_v1.include_router(models_router, prefix="/v1")
router_v1.include_router(admin_router, prefix="/v1")
router_v1.include_router(llm_router, prefix="/v1")
router_v1.include_router(groups_router, prefix="/v1")

