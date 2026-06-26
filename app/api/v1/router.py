from fastapi import APIRouter

from app.api.v1 import (
    analysis_router,
    auth_router,
    character_router,
    health_metric_router,
    home_router,
    mission_router,
    my_router,
    notification_router,
    ocr_router,
    onboarding_router,
    record_router,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router.router, prefix="/auth", tags=["Auth"])
api_router.include_router(onboarding_router.router, prefix="/onboarding", tags=["Onboarding"])
api_router.include_router(home_router.router, prefix="/home", tags=["Home"])
api_router.include_router(mission_router.router, prefix="/missions", tags=["Mission"])
api_router.include_router(record_router.router, prefix="/records", tags=["Record"])
api_router.include_router(ocr_router.router, prefix="/ocr", tags=["OCR"])
api_router.include_router(analysis_router.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(character_router.router, prefix="/characters", tags=["Character"])
api_router.include_router(my_router.router, prefix="/my", tags=["My"])
api_router.include_router(
    health_metric_router.router, prefix="/health-metrics", tags=["HealthMetric"]
)
api_router.include_router(
    notification_router.router, prefix="/notifications", tags=["Notification"]
)
