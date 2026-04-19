FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps ./apps
COPY shared ./shared

CMD uvicorn apps.forecast_service.app.main:app --host 0.0.0.0 --port ${PORT:-8000}

