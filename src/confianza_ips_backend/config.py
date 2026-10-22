from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./confianza.db"
    database_url_unpooled: str | None = None
    jwt_secret: str = "development-only-change-this-secret"
    jwt_expire_minutes: int = Field(default=30, ge=5, le=1440)
    waylo_totp_secret: str = ""
    waylo_totp_interval_seconds: int = Field(default=60, ge=30, le=3600)
    waylo_jwt_secret: str = ""
    waylo_token_expire_minutes: int = Field(default=15, ge=5, le=1440)
    cors_origins: str = "http://localhost:5173"
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
