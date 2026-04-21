from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.forecast_service.app.api import router as api_router
from shared.logging.setup import configure_logging


configure_logging()

app = FastAPI(title="PharmaForecast Forecast Service")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if any("quantity_on_hand" in error.get("loc", ()) for error in exc.errors()):
        return JSONResponse(
            status_code=422,
            content={
                "error": "INVALID_REQUEST",
                "message": "quantity_on_hand is required and must be 0 or greater",
            },
        )
    return await request_validation_exception_handler(request, exc)


app.include_router(api_router)
