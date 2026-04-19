from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def load_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def cached_settings() -> Settings:
    return load_settings()
