from fastapi import APIRouter
from fastapi.responses import JSONResponse

from apps.forecast_service.app.schemas.backtest import BacktestUploadRequest
from apps.forecast_service.app.services.backtesting import run_uploaded_backtest


router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/upload")
def backtest_upload(request: BacktestUploadRequest):
    payload = run_uploaded_backtest(request)
    status_code = 500 if payload["status"] == "ERROR" else 200
    return JSONResponse(status_code=status_code, content=payload)
