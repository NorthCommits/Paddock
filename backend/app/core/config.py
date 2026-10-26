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
    app_origin: str = "http://localhost:3000"
    content_origin: str = "http://localhost:8001"

    # Upload limits (see SDD section 5.1)
    max_bundle_bytes: int = 25 * 1024 * 1024
    max_file_bytes: int = 10 * 1024 * 1024
    max_files: int = 200

    # Where uploaded files live. Only local disk is built so far (see SDD section 8).
    storage_backend: str = "local"
    storage_local_path: str = "storage"

    # How long a signed link to published content stays valid.
    content_token_minutes: int = 15

    # Neon Auth. Sign up, sign in and password reset live there. The address looks like
    # https://ep-xxx.neonauth.<region>.aws.neon.tech/<database>/auth
    neon_auth_url: str | None = None
    # Set to true only when Neon is set to require a verified email before sign in.
    neon_auth_email_verified: bool = False

    # Email, used for page invitations. "console" only logs messages (development).
    # "smtp" sends them for real.
    email_backend: str = "console"
    email_from: str = "Paddock <noreply@localhost>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_security: str = "starttls"  # starttls, ssl or none

    @property
    def migration_url(self) -> str:
        return self.database_url_unpooled or self.database_url

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.secret_key == DEV_SECRET:
            raise ValueError("SECRET_KEY must be set in production")
        if self.email_backend not in ("console", "smtp"):
            raise ValueError("EMAIL_BACKEND must be console or smtp")
        if self.smtp_security not in ("starttls", "ssl", "none"):
            raise ValueError("SMTP_SECURITY must be starttls, ssl or none")
        if self.email_backend == "smtp" and not self.smtp_host:
            raise ValueError("SMTP_HOST must be set when EMAIL_BACKEND is smtp")
        if self.environment == "production" and not self.neon_auth_url:
            raise ValueError("NEON_AUTH_URL must be set in production")
        if self.environment == "production" and self.email_backend != "smtp":
            raise ValueError("EMAIL_BACKEND must be smtp in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
