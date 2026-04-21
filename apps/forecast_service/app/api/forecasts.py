from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

from apps.forecast_service.app.schemas.forecast import (
    BatchForecastRequest,
    DrugForecastRequest,
    NotificationCheckRequest,
)
from apps.forecast_service.app.services.forecasting import (
    FORECAST_CODE_PATH,
    batch_forecast,
    forecast_drug,
    notification_check,
)


router = APIRouter(prefix="/forecast", tags=["forecast"])


def _forecast_response(payload: dict):
    if "error" not in payload:
        return JSONResponse(status_code=200, content=payload, headers={"X-Forecast-Code-Path": FORECAST_CODE_PATH})
    status_code = 503 if payload["error"] == "forecast_timeout" else 422
    return JSONResponse(status_code=status_code, content=payload, headers={"X-Forecast-Code-Path": FORECAST_CODE_PATH})


@router.post("/drug")
def predict_drug(request: DrugForecastRequest):
    return _forecast_response(forecast_drug(request))


@router.post("/batch")
def predict_batch(request: BatchForecastRequest):
    return StreamingResponse(
        batch_forecast(request),
        media_type="text/event-stream",
        headers={"X-Forecast-Code-Path": FORECAST_CODE_PATH},
    )


@router.post("/notification-check")
def predict_notification_check(request: NotificationCheckRequest):
    return notification_check(request)
