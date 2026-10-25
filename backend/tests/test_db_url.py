from app.db.url import prepare_database_url

NEON_POOLED = (
    "postgresql://user:pw@ep-test-pooler.us-east-2.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)
NEON_DIRECT = "postgresql://user:pw@ep-test.us-east-2.aws.neon.tech/neondb?sslmode=require"


def test_driver_is_switched_to_asyncpg():
    url, _ = prepare_database_url(NEON_DIRECT)
    assert url.startswith("postgresql+asyncpg://")


def test_ssl_options_move_out_of_the_address():
    url, args = prepare_database_url(NEON_POOLED)
    assert "sslmode" not in url
    assert "channel_binding" not in url
    assert args["ssl"] == "require"


def test_pooled_address_turns_off_statement_caches():
    _, args = prepare_database_url(NEON_POOLED)
    assert args["statement_cache_size"] == 0
    assert args["prepared_statement_cache_size"] == 0


def test_direct_address_keeps_default_caches():
    _, args = prepare_database_url(NEON_DIRECT)
    assert "statement_cache_size" not in args


def test_plain_local_address_has_no_ssl():
    url, args = prepare_database_url("postgresql://u:p@localhost:5432/db")
    assert args == {}
    assert url == "postgresql+asyncpg://u:p@localhost:5432/db"
