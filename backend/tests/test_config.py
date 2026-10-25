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
    )
    assert s.environment == "production"


def test_migrations_prefer_the_unpooled_address():
    s = Settings(
        database_url="postgresql://pooled/db",
        database_url_unpooled="postgresql://direct/db",
    )
    assert s.migration_url == "postgresql://direct/db"


def test_migrations_fall_back_to_the_main_address():
    s = Settings(database_url="postgresql://pooled/db", database_url_unpooled=None)
    assert s.migration_url == "postgresql://pooled/db"
