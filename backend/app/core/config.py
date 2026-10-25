from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-change-me"


class Settings(BaseSettings):
    """All configuration comes from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    # Neon gives two addresses: pooled (for the app) and unpooled (for migrations).
    database_url: str
    database_url_unpooled: str | None = None

    secret_key: str = DEV_SECRET
    session_days: int = 30
    app_origin: str = "http://localhost:3000"
    content_origin: str = "http://localhost:8001"

    # Upload limits (see SDD section 5.1)
    max_bundle_bytes: int = 25 * 1024 * 1024
    max_file_bytes: int = 10 * 1024 * 1024
    max_files: int = 200

    @property
    def cookie_secure(self) -> bool:
        """Browsers only send secure cookies over HTTPS, so switch it off for local work."""
        return self.environment not in ("development", "test")

    @property
    def migration_url(self) -> str:
        return self.database_url_unpooled or self.database_url

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.secret_key == DEV_SECRET:
            raise ValueError("SECRET_KEY must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
