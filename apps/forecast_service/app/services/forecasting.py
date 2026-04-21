from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Iterator

from apps.forecast_service.app.schemas.forecast import (
    BatchForecastRequest,
    DrugForecastRequest,
    NotificationCheckRequest,
)
from apps.forecast_service.app.services.domain import ForecastResult
from apps.forecast_service.app.services.history import DemandHistoryPreparer
from apps.forecast_service.app.services.model import ForecastModelRunner, XGBoostModelRunner
from apps.forecast_service.app.services.repository import DispensingRepository, SupabaseDispensingRepository


logger = logging.getLogger(__name__)
FORECAST_TIMEOUT_SECONDS = 30
DEFAULT_RED_THRESHOLD_DAYS = 3
DEFAULT_AMBER_THRESHOLD_DAYS = 7
FORECAST_CODE_PATH = "weekly-xgboost-residual-v1"


def build_insufficient_data_response() -> dict[str, Any]:
    return {"error": "insufficient_data", "minimum_rows": 14, "confidence": "LOW"}


def build_invalid_forecast_response() -> dict[str, Any]:
    return {
        "error": "invalid_forecast_output",
        "confidence": "LOW",
        "details": "prophet_lower must be less than or equal to prophet_upper and both must be non-negative",
    }


class ForecastEngine:
    def __init__(
        self,
        repository: DispensingRepository,
        model_runner: ForecastModelRunner,
        history_preparer: DemandHistoryPreparer | None = None,
        timeout_seconds: int = FORECAST_TIMEOUT_SECONDS,
    ) -> None:
        self.repository = repository
        self.model_runner = model_runner
        self.history_preparer = history_preparer or DemandHistoryPreparer()
        self.timeout_seconds = timeout_seconds

    def forecast_drug(self, request: DrugForecastRequest) -> dict[str, Any]:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._forecast_drug_without_timeout, request)
        try:
            return future.result(timeout=self.timeout_seconds)
        except TimeoutError:
            future.cancel()
            logger.warning(
                "forecast_timeout",
                extra={
                    "din": request.din,
                    "location_id": request.location_id,
                    "timeout_seconds": self.timeout_seconds,
                },
            )
            return {"error": "forecast_timeout", "confidence": "LOW"}
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _forecast_drug_without_timeout(self, request: DrugForecastRequest) -> dict[str, Any]:
        started_at = time.perf_counter()
        rows = self.repository.fetch_dispensing_rows(request.location_id, request.din)
        self._log_fetch_summary(request.din, request.location_id, rows)
        return self._forecast_drug_from_rows(request, rows, started_at)

    def _forecast_drug_from_rows(
        self, request: DrugForecastRequest, rows: list[dict[str, Any]], started_at: float | None = None
    ) -> dict[str, Any]:
        started_at = started_at if started_at is not None else time.perf_counter()
        if len(rows) < 14:
            return build_insufficient_data_response()

        weekly_rows = self.history_preparer.weekly_totals(rows)
        weekly_rows = self.history_preparer.merge_supplemental_history(weekly_rows, request.supplemental_history)
        prediction = self.model_runner.forecast(weekly_rows, request.horizon_days)

        avg_daily_demand = round(prediction.predicted_quantity / max(request.horizon_days, 1), 1)
        days_of_supply = round(request.quantity_on_hand / max(avg_daily_demand, 0.1), 1)
        reorder_point = round(avg_daily_demand * request.lead_time_days * request.safety_multiplier, 1)
        reorder_status = _reorder_status(
            days_of_supply,
            red_threshold_days=request.red_threshold_days,
            amber_threshold_days=request.amber_threshold_days,
        )

        result = ForecastResult(
            din=request.din,
            location_id=request.location_id,
            horizon_days=request.horizon_days,
            predicted_quantity=prediction.predicted_quantity,
            prophet_lower=prediction.prophet_lower,
            prophet_upper=prediction.prophet_upper,
            confidence=prediction.confidence,
            model_path=prediction.model_path,
            days_of_supply=days_of_supply,
            avg_daily_demand=avg_daily_demand,
            reorder_status=reorder_status,
            reorder_point=reorder_point,
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_points_used=len(rows),
        ).__dict__

        if not self._is_publishable_result(result):
            logger.warning(
                "forecast_rejected",
                extra={
                    "din": request.din,
                    "location_id": request.location_id,
                    "horizon_days": request.horizon_days,
                    "reason": "invalid_forecast_output",
                },
            )
            return build_invalid_forecast_response()

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "forecast_completed",
            extra={
                "forecast_code_path": FORECAST_CODE_PATH,
                "din": request.din,
                "location_id": request.location_id,
                "horizon_days": request.horizon_days,
                "duration_ms": duration_ms,
                "data_points_used": len(rows),
            },
        )
        return result

    @staticmethod
    def _is_publishable_result(result: dict[str, Any]) -> bool:
        return (
            int(result["predicted_quantity"]) >= 0
            and int(result["prophet_lower"]) >= 0
            and int(result["prophet_upper"]) >= 0
            and int(result["prophet_lower"]) <= int(result["prophet_upper"])
            and float(result["days_of_supply"]) >= 0
            and int(result["data_points_used"]) >= 14
        )

    def batch_forecast(self, request: BatchForecastRequest) -> Iterator[str]:
        succeeded = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self._forecast_batch_din, request, din): din for din in request.dins}
            for future in as_completed(futures):
                din = futures[future]
                try:
                    result = future.result()
                    if "error" in result:
                        failed += 1
                        yield _sse_event({"din": din, "status": "error", "error": result["error"]})
                    else:
                        succeeded += 1
                        yield _sse_event({"din": din, "status": "complete", "result": result})
                except Exception as exc:  # pragma: no cover - defensive stream failure path
                    failed += 1
                    yield _sse_event({"din": din, "status": "error", "error": str(exc)})
        yield _sse_event({"status": "done", "total": len(request.dins), "succeeded": succeeded, "failed": failed})

    def _forecast_batch_din(self, request: BatchForecastRequest, din: str) -> dict[str, Any]:
        threshold = request.thresholds.get(din)
        sub_request = DrugForecastRequest(
            location_id=request.location_id,
            din=din,
            horizon_days=request.horizon_days,
            quantity_on_hand=0,
            lead_time_days=threshold.lead_time_days if threshold else 2,
            safety_multiplier=threshold.safety_multiplier if threshold else 1.0,
            red_threshold_days=threshold.red_threshold_days if threshold else DEFAULT_RED_THRESHOLD_DAYS,
            amber_threshold_days=threshold.amber_threshold_days if threshold else DEFAULT_AMBER_THRESHOLD_DAYS,
            supplemental_history=None,
        )
        return self.forecast_drug(sub_request)

    def notification_check(self, request: NotificationCheckRequest) -> dict[str, Any]:
        alerts = []
        for din in self.repository.fetch_distinct_dins(request.location_id):
            sub_request = DrugForecastRequest(
                location_id=request.location_id,
                din=din,
                horizon_days=7,
                quantity_on_hand=0,
                lead_time_days=2,
                safety_multiplier=1.0,
                red_threshold_days=DEFAULT_RED_THRESHOLD_DAYS,
                amber_threshold_days=DEFAULT_AMBER_THRESHOLD_DAYS,
                supplemental_history=None,
            )
            rows = self.repository.fetch_dispensing_rows(request.location_id, din)
            if sub_request.quantity_on_hand == 0 and not self.history_preparer.has_activity_in_last_30_days(rows):
                continue

            result = self._forecast_drug_from_rows(sub_request, rows)
            if result.get("reorder_status") in {"RED", "AMBER"}:
                alerts.append(
                    {
                        "din": din,
                        "reorder_status": result["reorder_status"],
                        "days_of_supply": result["days_of_supply"],
                        "predicted_quantity": result["predicted_quantity"],
                    }
                )
        return {"alerts": alerts}

    @staticmethod
    def _log_fetch_summary(din: str, location_id: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            logger.info(
                "forecast_history_fetched",
                extra={
                    "forecast_code_path": FORECAST_CODE_PATH,
                    "din": din,
                    "location_id": location_id,
                    "record_count": 0,
                },
            )
            return

        start_date = min(row["dispensed_date"] for row in rows)
        end_date = max(row["dispensed_date"] for row in rows)
        total_quantity = sum(float(row.get("quantity_dispensed", 0)) for row in rows)
        logger.info(
            "forecast_history_fetched",
            extra={
                "forecast_code_path": FORECAST_CODE_PATH,
                "din": din,
                "location_id": location_id,
                "record_count": len(rows),
                "date_range_start": start_date,
                "date_range_end": end_date,
                "total_quantity": round(total_quantity, 2),
            },
        )


def _sse_event(payload: dict[str, Any]) -> str:
    return "data: " + json.dumps(payload, separators=(",", ":")) + "\n\n"


def _reorder_status(days_of_supply: float, red_threshold_days: int, amber_threshold_days: int) -> str:
    if days_of_supply <= red_threshold_days:
        return "RED"
    if days_of_supply <= amber_threshold_days:
        return "AMBER"
    return "GREEN"


def create_default_engine() -> ForecastEngine:
    return ForecastEngine(
        repository=SupabaseDispensingRepository(),
        model_runner=XGBoostModelRunner(),
    )


_default_engine: ForecastEngine | None = None


def get_default_engine() -> ForecastEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = create_default_engine()
    return _default_engine


def forecast_drug(request: DrugForecastRequest) -> dict[str, Any]:
    return get_default_engine().forecast_drug(request)


def batch_forecast(request: BatchForecastRequest) -> Iterator[str]:
    return get_default_engine().batch_forecast(request)


def notification_check(request: NotificationCheckRequest) -> dict[str, Any]:
    return get_default_engine().notification_check(request)
