import atexit
import os
import shutil
import tempfile


def _start_test_database() -> str:
    """Use TEST_DATABASE_URL if given, else start a throwaway local Postgres."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    import pixeltable_pgserver

    data_dir = tempfile.mkdtemp(prefix="paddock_test_pg_")
    server = pixeltable_pgserver.get_server(data_dir, cleanup_mode="stop")
    atexit.register(shutil.rmtree, data_dir, ignore_errors=True)
    return server.get_uri()


# Tests must never reach the real Neon database. Real environment variables win over
# backend/.env, so setting them here overrides the file.
TEST_DB_URL = _start_test_database()
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["DATABASE_URL_UNPOOLED"] = TEST_DB_URL
os.environ["ENVIRONMENT"] = "test"
STORAGE_DIR = tempfile.mkdtemp(prefix="paddock_test_files_")
os.environ["STORAGE_LOCAL_PATH"] = STORAGE_DIR
atexit.register(shutil.rmtree, STORAGE_DIR, ignore_errors=True)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

# Stands in for Neon's signing key. Tokens made with it pass the real checking code.
TEST_PRIVATE_KEY = Ed25519PrivateKey.generate()

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.content import app as content_app  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_engine, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services import mailer  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _create_schema():
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
async def _empty_tables():
    yield
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with get_engine().begin() as conn:
        await conn.execute(text(f"truncate {names} restart identity cascade"))


@pytest.fixture
async def client():
    """A client talking to the app with the real test database."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def content_client():
    """A client talking to the content gateway (a separate app, like in production)."""
    async with AsyncClient(
        transport=ASGITransport(app=content_app), base_url="http://content"
    ) as c:
        yield c


class FakeSession:
    """Stands in for a database session when a test does not need a real one."""

    def __init__(self, fail: bool = False):
        self.fail = fail

    async def execute(self, *_args, **_kwargs):
        if self.fail:
            raise ConnectionError("database down")


@pytest.fixture
def fake_session():
    return FakeSession()


@pytest.fixture
async def fake_client(fake_session):
    async def override():
        yield fake_session

    app.dependency_overrides[get_session] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def neon_keys(monkeypatch):
    """Use the test key instead of fetching Neon's public keys over the network."""
    from app.core import neon

    monkeypatch.setattr(neon, "_signing_key", lambda token: TEST_PRIVATE_KEY.public_key())


@pytest.fixture(autouse=True)
def outbox():
    """Every test gets an empty in-memory mailbox instead of real email."""
    box = mailer.MemoryMailer()
    mailer.set_mailer(box)
    return box
