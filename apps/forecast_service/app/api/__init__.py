from fastapi import APIRouter

from apps.forecast_service.app.api.backtests import router as backtests_router
from apps.forecast_service.app.api.forecasts import router as forecasts_router
from apps.forecast_service.app.api.health import router as health_router


router = APIRouter()
router.include_router(health_router)
router.include_router(forecasts_router)
router.include_router(backtests_router)
