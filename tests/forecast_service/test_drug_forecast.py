from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from apps.forecast_service.app.main import app
from apps.forecast_service.app.services.domain import ForecastPrediction
from apps.forecast_service.app.services.forecasting import ForecastEngine
from apps.forecast_service.app.services.model import (
    ProphetModelRunner,
    XGBoostModelRunner,
    normalize_weekly_history,
    summarize_horizon_forecast,
)


class _FakeRepository:
    def __init__(self, rows_by_din=None, dins=None):
        self.rows_by_din = rows_by_din or {}
        self.dins = dins or sorted(self.rows_by_din)

    def fetch_dispensing_rows(self, _location_id, din):
        rows = self.rows_by_din.get(din, [])
        if isinstance(rows, Exception):
            raise rows
        return rows

    def fetch_distinct_dins(self, _location_id):
        return self.dins


class _FakeModelRunner:
    def __init__(self, prediction=None):
        self.prediction = prediction or ForecastPrediction(
            predicted_quantity=21,
            prophet_lower=18,
            prophet_upper=24,
            confidence="MEDIUM",
            model_path="prophet",
        )
        self.weekly_rows = None

    def forecast(self, weekly_rows, _horizon_days):
        self.weekly_rows = weekly_rows
        return self.prediction


class _ExplodingModelRunner:
    def forecast(self, _weekly_rows, _horizon_days):
        raise AssertionError("forecast should not run")


class _InvalidModelRunner:
    def forecast(self, _weekly_rows, _horizon_days):
        return ForecastPrediction(
            predicted_quantity=12,
            prophet_lower=0,
            prophet_upper=-345,
            confidence="LOW",
            model_path="prophet",
        )


class _FakeEndpointEngine:
    def notification_check(self, _request):
        return {
            "alerts": [
                {
                    "din": "11111111",
                    "reorder_status": "RED",
                    "days_of_supply": 2.0,
                    "predicted_quantity": 10,
                }
            ]
        }


def _rows(count, quantity=2):
    return [
        {
            "dispensed_date": (date(2026, 3, 1) + timedelta(days=offset)).isoformat(),
            "quantity_dispensed": quantity,
        }
        for offset in range(count)
    ]


def _old_rows(count, quantity=2):
    start = datetime.now(timezone.utc).date() - timedelta(days=60)
    return [
        {
            "dispensed_date": (start + timedelta(days=offset)).isoformat(),
            "quantity_dispensed": quantity,
        }
        for offset in range(count)
    ]


def _install_engine(monkeypatch, engine):
    from apps.forecast_service.app.services import forecasting

    monkeypatch.setattr(forecasting, "get_default_engine", lambda: engine)


def test_single_drug_forecast_rejects_insufficient_history(monkeypatch):
    engine = ForecastEngine(
        repository=_FakeRepository({"12345678": _rows(1, quantity=3)}),
        model_runner=_FakeModelRunner(),
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "horizon_days": 7,
            "quantity_on_hand": 10,
            "lead_time_days": 2,
            "safety_multiplier": 1.0,
            "supplemental_history": None,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "insufficient_data",
        "minimum_rows": 14,
        "confidence": "LOW",
    }


def test_single_drug_forecast_returns_custom_validation_error_for_missing_quantity():
    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "horizon_days": 7,
            "lead_time_days": 2,
            "safety_multiplier": 1.0,
            "supplemental_history": None,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "INVALID_REQUEST",
        "message": "quantity_on_hand is required and must be 0 or greater",
    }


def test_single_drug_forecast_returns_custom_validation_error_for_negative_quantity():
    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "horizon_days": 7,
            "quantity_on_hand": -1,
            "lead_time_days": 2,
            "safety_multiplier": 1.0,
            "supplemental_history": None,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "INVALID_REQUEST",
        "message": "quantity_on_hand is required and must be 0 or greater",
    }


def test_single_drug_forecast_returns_operational_metrics(monkeypatch):
    engine = ForecastEngine(
        repository=_FakeRepository({"12345678": _rows(30)}),
        model_runner=_FakeModelRunner(),
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "horizon_days": 14,
            "quantity_on_hand": 30,
            "lead_time_days": 2,
            "safety_multiplier": 1.0,
            "supplemental_history": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["din"] == "12345678"
    assert payload["location_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["horizon_days"] == 14
    assert payload["predicted_quantity"] == 21
    assert payload["prophet_lower"] == 18
    assert payload["prophet_upper"] == 24
    assert payload["confidence"] == "MEDIUM"
    assert payload["days_of_supply"] == 20.0
    assert payload["avg_daily_demand"] == 1.5
    assert payload["reorder_status"] == "GREEN"
    assert payload["reorder_point"] == 3.0
    assert payload["data_points_used"] == 30
    assert payload["model_path"] == "prophet"
    assert payload["generated_at"].endswith("+00:00")
    assert response.headers["x-forecast-code-path"] == "weekly-xgboost-residual-v1"


def test_single_drug_forecast_uses_explicit_reorder_thresholds(monkeypatch):
    engine = ForecastEngine(
        repository=_FakeRepository({"12345678": _rows(30)}),
        model_runner=_FakeModelRunner(
            ForecastPrediction(
                predicted_quantity=140,
                prophet_lower=130,
                prophet_upper=150,
                confidence="MEDIUM",
                model_path="prophet",
            )
        ),
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "horizon_days": 14,
            "quantity_on_hand": 69,
            "lead_time_days": 2,
            "safety_multiplier": 1.0,
            "red_threshold_days": 3,
            "amber_threshold_days": 7,
            "supplemental_history": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["avg_daily_demand"] == 10.0
    assert payload["days_of_supply"] == 6.9
    assert payload["reorder_status"] == "AMBER"


def test_single_drug_forecast_uses_request_stock_for_days_of_supply(monkeypatch):
    engine = ForecastEngine(
        repository=_FakeRepository({"00123456": _rows(30)}),
        model_runner=_FakeModelRunner(
            ForecastPrediction(
                predicted_quantity=781,
                prophet_lower=770,
                prophet_upper=790,
                confidence="HIGH",
                model_path="prophet",
            )
        ),
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "00123456",
            "horizon_days": 14,
            "quantity_on_hand": 124,
            "lead_time_days": 2,
            "safety_multiplier": 1.5,
            "supplemental_history": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["avg_daily_demand"] == 55.8
    assert payload["days_of_supply"] == 2.2
    assert payload["reorder_status"] == "RED"
    assert payload["reorder_point"] == 167.4


def test_single_drug_forecast_rejects_invalid_model_interval(monkeypatch):
    engine = ForecastEngine(
        repository=_FakeRepository({"12345678": _rows(30)}),
        model_runner=_InvalidModelRunner(),
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "horizon_days": 14,
            "quantity_on_hand": 30,
            "lead_time_days": 2,
            "safety_multiplier": 1.0,
            "supplemental_history": None,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "invalid_forecast_output",
        "confidence": "LOW",
        "details": "prophet_lower must be less than or equal to prophet_upper and both must be non-negative",
    }


def test_batch_forecast_streams_completion_events(monkeypatch):
    engine = ForecastEngine(
        repository=_FakeRepository(
            {
                "11111111": _rows(30),
                "22222222": RuntimeError("boom"),
            }
        ),
        model_runner=_FakeModelRunner(
            ForecastPrediction(
                predicted_quantity=10,
                prophet_lower=8,
                prophet_upper=12,
                confidence="HIGH",
                model_path="prophet",
            )
        ),
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    with client.stream(
        "POST",
        "/forecast/batch",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "dins": ["11111111", "22222222"],
            "horizon_days": 7,
            "thresholds": {
                "11111111": {"lead_time_days": 2, "safety_multiplier": 1.0},
                "22222222": {"lead_time_days": 2, "safety_multiplier": 1.0},
            },
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode()

    assert 'data: {"din":"11111111","status":"complete"' in body
    assert '"predicted_quantity":10' in body
    assert 'data: {"din":"22222222","status":"error","error":"boom"}' in body
    assert 'data: {"status":"done","total":2,"succeeded":1,"failed":1}' in body


def test_batch_forecast_streams_structured_forecast_errors(monkeypatch):
    engine = ForecastEngine(
        repository=_FakeRepository({"11111111": _rows(1)}),
        model_runner=_FakeModelRunner(),
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    with client.stream(
        "POST",
        "/forecast/batch",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "dins": ["11111111"],
            "horizon_days": 7,
            "thresholds": {
                "11111111": {"lead_time_days": 2, "safety_multiplier": 1.0},
            },
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode()

    assert 'data: {"din":"11111111","status":"error","error":"insufficient_data"}' in body
    assert 'data: {"status":"done","total":1,"succeeded":0,"failed":1}' in body


def test_batch_forecast_streams_invalid_model_interval_as_error(monkeypatch):
    engine = ForecastEngine(
        repository=_FakeRepository({"11111111": _rows(30)}),
        model_runner=_InvalidModelRunner(),
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    with client.stream(
        "POST",
        "/forecast/batch",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "dins": ["11111111"],
            "horizon_days": 7,
            "thresholds": {
                "11111111": {"lead_time_days": 2, "safety_multiplier": 1.0},
            },
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode()

    assert 'data: {"din":"11111111","status":"error","error":"invalid_forecast_output"}' in body
    assert 'data: {"status":"done","total":1,"succeeded":0,"failed":1}' in body


def test_supplemental_history_is_merged_before_model_forecast(monkeypatch):
    model = _FakeModelRunner()
    engine = ForecastEngine(
        repository=_FakeRepository({"12345678": _rows(14)}),
        model_runner=model,
    )
    _install_engine(monkeypatch, engine)

    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "horizon_days": 7,
            "quantity_on_hand": 30,
            "lead_time_days": 2,
            "safety_multiplier": 1.0,
            "supplemental_history": [{"week": "2026-03-02", "quantity": 5}],
        },
    )

    assert response.status_code == 200
    assert model.weekly_rows[0] == {"ds": date(2026, 2, 23), "y": 2.0}
    assert model.weekly_rows[1] == {"ds": date(2026, 3, 2), "y": 19.0}


def test_horizon_forecast_uses_samples_to_build_a_valid_interval():
    forecast_window = pd.DataFrame(
        {
            "yhat": [10.2, 11.8],
            "yhat_lower": [-50.0, -25.0],
            "yhat_upper": [-40.0, -10.0],
        }
    )
    predictive_samples = {"yhat": np.array([[9.5, 10.5, 11.0], [10.5, 11.5, 12.0]])}

    prediction = summarize_horizon_forecast(
        forecast_window,
        horizon_periods=2,
        predictive_samples=predictive_samples,
    )

    assert prediction.predicted_quantity == 22
    assert prediction.prophet_lower >= 0
    assert prediction.prophet_upper >= 0
    assert prediction.prophet_lower <= prediction.prophet_upper


def test_prophet_runner_uses_non_negative_fallback_for_short_weekly_history():
    quantities = [
        180,
        195,
        210,
        220,
        215,
        200,
        185,
        170,
        155,
        145,
        130,
        120,
        110,
        100,
        90,
        80,
        75,
        70,
        68,
    ]
    weekly_rows = [
        {"ds": date(2026, 1, 5) + timedelta(days=7 * offset), "y": quantity}
        for offset, quantity in enumerate(quantities)
    ]

    prediction = ProphetModelRunner().forecast(weekly_rows, horizon_days=7)

    assert prediction.predicted_quantity == 66
    assert prediction.model_path == "fallback_recent_trend"
    assert prediction.prophet_lower >= 0
    assert prediction.prophet_lower <= prediction.predicted_quantity <= prediction.prophet_upper
    assert prediction.confidence in {"LOW", "MEDIUM", "HIGH"}


def test_xgboost_runner_returns_calibrated_non_negative_interval():
    quantities = [20, 21, 23, 22, 24, 25, 27, 26, 28, 30, 31, 30, 32, 33, 35, 34]
    weekly_rows = [
        {"ds": date(2026, 1, 5) + timedelta(days=7 * offset), "y": quantity}
        for offset, quantity in enumerate(quantities)
    ]

    prediction = XGBoostModelRunner().forecast(weekly_rows, horizon_days=7)

    assert prediction.model_path == "xgboost_residual_interval"
    assert prediction.predicted_quantity >= 0
    assert prediction.prophet_lower >= 0
    assert prediction.prophet_lower <= prediction.predicted_quantity <= prediction.prophet_upper
    assert prediction.confidence in {"LOW", "MEDIUM", "HIGH"}


def test_normalize_weekly_history_aggregates_raw_rows_by_week_start():
    frame = normalize_weekly_history(
        [
            {"dispensed_date": "2026-01-21", "quantity_dispensed": 50},
            {"dispensed_date": "2026-01-22", "quantity_dispensed": 25},
            {"dispensed_date": "2026-01-28", "quantity_dispensed": 10},
        ]
    )

    assert list(frame["ds"].dt.date) == [date(2026, 1, 19), date(2026, 1, 26)]
    assert list(frame["y"]) == [75.0, 10.0]


def test_notification_check_returns_only_actionable_alerts(monkeypatch):
    from apps.forecast_service.app.services import forecasting

    monkeypatch.setattr(forecasting, "get_default_engine", lambda: _FakeEndpointEngine())

    client = TestClient(app)

    response = client.post(
        "/forecast/notification-check",
        json={"location_id": "11111111-1111-1111-1111-111111111111"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "alerts": [
            {
                "din": "11111111",
                "reorder_status": "RED",
                "days_of_supply": 2.0,
                "predicted_quantity": 10,
            }
        ]
    }


def test_notification_check_skips_zero_stock_din_with_no_recent_activity():
    engine = ForecastEngine(
        repository=_FakeRepository({"11111111": _old_rows(14)}, dins=["11111111"]),
        model_runner=_ExplodingModelRunner(),
    )

    assert engine.notification_check(
        type("Request", (), {"location_id": "11111111-1111-1111-1111-111111111111"})()
    ) == {"alerts": []}
