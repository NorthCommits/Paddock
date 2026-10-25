import pytest

from app.core.config import Settings


def test_production_requires_a_real_secret():
    with pytest.raises(ValueError):
        Settings(database_url="postgresql://u:p@h/db", environment="production")


def test_production_accepts_a_real_secret():
    s = Settings(
        database_url="postgresql://u:p@h/db",
        environment="production",
        secret_key="x" * 40,
        email_backend="smtp",
        smtp_host="smtp.example.com",
    )
    assert s.environment == "production"


def test_production_needs_real_email_sending():
    with pytest.raises(ValueError):
        Settings(
            database_url="postgresql://u:p@h/db", environment="production", secret_key="x" * 40
        )


def test_smtp_needs_a_host():
    with pytest.raises(ValueError):
        Settings(database_url="postgresql://u:p@h/db", email_backend="smtp")


def test_email_options_are_checked():
    with pytest.raises(ValueError):
        Settings(database_url="postgresql://u:p@h/db", email_backend="carrier-pigeon")
    with pytest.raises(ValueError):
        Settings(database_url="postgresql://u:p@h/db", smtp_security="maybe")


def test_migrations_prefer_the_unpooled_address():
    s = Settings(
        database_url="postgresql://pooled/db",
        database_url_unpooled="postgresql://direct/db",
    )
    assert s.migration_url == "postgresql://direct/db"


def test_migrations_fall_back_to_the_main_address():
    s = Settings(database_url="postgresql://pooled/db", database_url_unpooled=None)
    assert s.migration_url == "postgresql://pooled/db"
