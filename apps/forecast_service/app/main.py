from fastapi import FastAPI

from apps.forecast_service.app.api import router as api_router
from shared.logging.setup import configure_logging


configure_logging()

app = FastAPI(title="PharmaForecast Forecast Service")
app.include_router(api_router)

