from fastapi import APIRouter

from app.routes.v1.config import router as config_router

router = APIRouter()
router.include_router(config_router)
