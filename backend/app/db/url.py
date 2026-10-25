from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def prepare_database_url(raw: str) -> tuple[str, dict]:
    """Turn a Neon address into what SQLAlchemy and asyncpg accept.

    Neon gives: postgresql://user:pass@host/db?sslmode=require&channel_binding=require
    asyncpg does not understand sslmode or channel_binding in the address, so we
    remove them and pass the ssl setting as a connection argument instead.

    The pooled Neon address (host contains "-pooler") goes through PgBouncer, so we
    switch off the driver's prepared statement caches to stay safe.
    """
    parts = urlsplit(raw)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)

    url = urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), ""))

    connect_args: dict = {}
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = sslmode
    if "-pooler" in (parts.hostname or ""):
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
    return url, connect_args
