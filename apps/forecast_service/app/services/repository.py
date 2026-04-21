from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol

from apps.forecast_service.app.services.domain import ForecastingError
from shared.config.settings import cached_settings


class DispensingRepository(Protocol):
    def fetch_dispensing_rows(self, location_id: str, din: str) -> list[dict[str, Any]]:
        ...

    def fetch_distinct_dins(self, location_id: str) -> list[str]:
        ...


@lru_cache(maxsize=1)
def get_supabase_client() -> Any:
    settings = cached_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise ForecastingError("supabase_not_configured")
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - optional runtime dependency
        raise ForecastingError("supabase_dependency_missing") from exc

    return create_client(settings.supabase_url, settings.supabase_service_key)


class SupabaseDispensingRepository:
    def fetch_dispensing_rows(self, location_id: str, din: str) -> list[dict[str, Any]]:
        client = get_supabase_client()
        result = (
            client.table("dispensing_records")
            .select("dispensed_date, quantity_dispensed")
            .eq("location_id", location_id)
            .eq("din", din)
            .order("dispensed_date", desc=False)
            .execute()
        )
        return list(getattr(result, "data", []) or [])

    def fetch_distinct_dins(self, location_id: str) -> list[str]:
        client = get_supabase_client()
        result = client.table("dispensing_records").select("din").eq("location_id", location_id).execute()
        dins = {row["din"] for row in (getattr(result, "data", []) or []) if row.get("din")}
        return sorted(dins)
