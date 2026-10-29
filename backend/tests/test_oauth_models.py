from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import ApiToken, OAuthClient, OAuthCode
from app.db.session import get_sessionmaker
from tests.helpers import signup


async def test_oauth_tables_and_token_columns_exist(client):
    data = await signup(client)
    from app.db.models import User

    async with get_sessionmaker()() as db:
        user = await db.scalar(select(User).where(User.handle == data["user"]["handle"]))
        db.add(
            OAuthClient(
                client_id="client-1",
                client_name="Claude",
                redirect_uris=["https://claude.ai/api/mcp/auth_callback"],
            )
        )
        manual = ApiToken(
            user_id=user.id,
            name="manual",
            prefix="pdk_aaaa",
            token_hash="a" * 64,
            scopes=["pages:read"],
        )
        oauth = ApiToken(
            user_id=user.id,
            name="Claude (connected with sign-in)",
            prefix="pdk_bbbb",
            token_hash="b" * 64,
            scopes=["pages:read"],
            client_id="client-1",
            source="oauth",
        )
        db.add_all([manual, oauth])
        await db.flush()
        db.add(
            OAuthCode(
                code_hash="c" * 64,
                client_id="client-1",
                user_id=user.id,
                redirect_uri="https://claude.ai/api/mcp/auth_callback",
                code_challenge="x" * 43,
                scopes=["pages:read"],
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
                token_id=oauth.id,
            )
        )
        await db.commit()
        assert manual.source == "manual"
        assert manual.client_id is None
        assert oauth.source == "oauth"
        code = await db.scalar(select(OAuthCode).where(OAuthCode.code_hash == "c" * 64))
        assert code.used_at is None
        assert code.token_id == oauth.id


def test_api_public_url_setting_defaults_to_local_api():
    assert get_settings().api_public_url == "http://localhost:8000"
