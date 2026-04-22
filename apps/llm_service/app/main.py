from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.llm_service.app.api import router as api_router
from shared.grok_client import GrokApiException
from shared.logging.setup import configure_logging


configure_logging()

app = FastAPI(title="PharmaForecast LLM Service")


@app.exception_handler(GrokApiException)
async def grok_exception_handler(request: Request, exc: GrokApiException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "LLM_ERROR", "message": exc.message},
    )


@app.exception_handler(ValueError)
async def validation_exception_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "error": "INVALID_PAYLOAD",
            "message": "Patient data is not permitted in LLM requests",
        },
    )


app.include_router(api_router)
