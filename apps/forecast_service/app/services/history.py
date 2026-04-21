from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from apps.forecast_service.app.services.domain import ForecastingError


def parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    raise ForecastingError("invalid_date")


def week_start_monday(value: date) -> date:
    return value - timedelta(days=value.weekday())


class DemandHistoryPreparer:
    def weekly_totals(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        totals: dict[date, float] = defaultdict(float)
        for row in rows:
            week = week_start_monday(parse_date(row["dispensed_date"]))
            totals[week] += float(row["quantity_dispensed"])
        return [{"ds": week, "y": total} for week, total in sorted(totals.items())]

    def merge_supplemental_history(
        self, weekly_rows: list[dict[str, Any]], supplemental_history: list[Any] | None
    ) -> list[dict[str, Any]]:
        if not supplemental_history:
            return weekly_rows

        merged = {row["ds"]: float(row["y"]) for row in weekly_rows}
        for item in supplemental_history:
            week_value = item.week if hasattr(item, "week") else item["week"]
            quantity = item.quantity if hasattr(item, "quantity") else item["quantity"]
            week = week_start_monday(parse_date(week_value))
            merged[week] = merged.get(week, 0.0) + float(quantity)
        return [{"ds": week, "y": total} for week, total in sorted(merged.items())]

    def avg_daily_demand_last_30_days(self, rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0

        end_date = max(parse_date(row["dispensed_date"]) for row in rows)
        cutoff = end_date - timedelta(days=29)
        total = 0.0
        for row in rows:
            dispensed = parse_date(row["dispensed_date"])
            if dispensed >= cutoff:
                total += float(row["quantity_dispensed"])
        return total / 30.0

    def has_activity_in_last_30_days(self, rows: list[dict[str, Any]], today: date | None = None) -> bool:
        if not rows:
            return False

        today = today or datetime.now(timezone.utc).date()
        cutoff = today - timedelta(days=29)
        return any(parse_date(row["dispensed_date"]) >= cutoff for row in rows)
