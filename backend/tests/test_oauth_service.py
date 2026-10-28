import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.db.models import ApiToken, OAuthCode, User
from app.db.session import get_sessionmaker
from app.services import oauth
from tests.helpers import signup

VERIFIER = "v" * 50
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)
REDIRECT = "https://app.example.com/cb"


async def _user(client):
    await signup(client)
    async with get_sessionmaker()() as db:
        return await db.scalar(select(User))


async def _register(db, name="Claude Desktop", uris=(REDIRECT,)):
    return await oauth.register_client(db, client_name=name, redirect_uris=list(uris))


async def _approve(db, user, app, redirect=REDIRECT, challenge=CHALLENGE):
    return await oauth.approve(
        db,
        user,
        app,
        redirect_uri=redirect,
        code_challenge=challenge,
        scopes=["pages:read", "pages:write"],
        ip="1.2.3.4",
    )


async def _exchange(db, app, code, verifier=VERIFIER, redirect=REDIRECT, client_id=None):
    return await oauth.exchange(
        db,
        client_id=client_id or app.client_id,
        code=code,
        code_verifier=verifier,
        redirect_uri=redirect,
        ip="1.2.3.4",
    )


def _check(app, **over):
    args = {
        "redirect_uri": REDIRECT,
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "scope": None,
        "response_type": "code",
    }
    args.update(over)
    return oauth.check_request(app, **args)


def test_redirect_ok_rules():
    assert oauth.redirect_ok("https://app.example.com/cb")
    assert oauth.redirect_ok("http://localhost:33445/cb")
    assert oauth.redirect_ok("http://127.0.0.1:8080/cb")
    assert oauth.redirect_ok("http://[::1]:8080/cb")
    assert oauth.redirect_ok("cursor://anysphere.cursor/oauth")
    assert not oauth.redirect_ok("http://evil.com/cb")
    assert not oauth.redirect_ok("javascript:alert(1)")
    assert not oauth.redirect_ok("data:text/html,hi")
    assert not oauth.redirect_ok("ab://x/y")
    assert not oauth.redirect_ok("not a uri")
    assert not oauth.redirect_ok("")


async def test_register_limits(client):
    async with get_sessionmaker()() as db:
        app = await _register(db)
        assert 0 < len(app.client_id) <= 64
        for name, uris in [
            ("x", []),
            ("x", [f"https://a.example.com/{i}" for i in range(11)]),
            ("x", ["https://a.example.com/" + "a" * 500]),
            ("n" * 101, [REDIRECT]),
            ("x", ["http://evil.com/cb"]),
        ]:
            with pytest.raises(oauth.OAuthError) as err:
                await oauth.register_client(db, client_name=name, redirect_uris=uris)
            assert err.value.code in ("invalid_redirect_uri", "invalid_client_metadata")


async def test_check_request_requires_exact_redirect_and_s256(client):
    async with get_sessionmaker()() as db:
        app = await _register(db, uris=[REDIRECT, "http://localhost:1234/cb"])
    assert _check(app) == list(oauth.OFFERED_SCOPES)
    assert _check(app, scope="pages:read") == ["pages:read"]

    def code_of(**over):
        with pytest.raises(oauth.OAuthError) as err:
            _check(app, **over)
        return err.value.code

    assert code_of(redirect_uri=REDIRECT + "/") == "invalid_request"
    assert code_of(code_challenge_method="plain") == "invalid_request"
    assert code_of(code_challenge="short") == "invalid_request"
    assert code_of(response_type="token") == "unsupported_response_type"
    assert code_of(scope="events:read") == "invalid_scope"
    # A loopback port may differ, but the path may not.
    _check(app, redirect_uri="http://localhost:55555/cb")
    assert code_of(redirect_uri="http://localhost:55555/other") == "invalid_request"
    assert code_of(redirect_uri="http://127.0.0.1:1234/cb") == "invalid_request"
    assert code_of(redirect_uri="https://app.example.com:444/cb") == "invalid_request"


async def test_exchange_happy_path_creates_oauth_token(client):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db, name="N" * 95)
        code = await _approve(db, user, app)
        token, scopes = await _exchange(db, app, code)
    assert token.startswith("pdk_")
    assert scopes == ["pages:read", "pages:write"]
    async with get_sessionmaker()() as db:
        row = await db.scalar(select(ApiToken))
        stored = await db.scalar(select(OAuthCode))
    assert row.source == "oauth"
    assert row.client_id == app.client_id
    assert row.name == ("N" * 95 + " (connected with sign-in)")[:100]
    assert row.expires_at is None
    assert stored.code_hash != code
    assert stored.token_id == row.id


async def test_code_is_single_use_and_reuse_revokes_token(client):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db)
        code = await _approve(db, user, app)
        await _exchange(db, app, code)
        with pytest.raises(oauth.OAuthError) as err:
            await _exchange(db, app, code)
    assert err.value.code == "invalid_grant"
    async with get_sessionmaker()() as db:
        assert (await db.scalar(select(ApiToken))).revoked_at is not None


async def test_code_expires_after_ten_minutes(client):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db)
        code = await _approve(db, user, app)
        row = await db.scalar(select(OAuthCode))
        assert timedelta(minutes=9) < row.expires_at - datetime.now(UTC) <= timedelta(minutes=10)
        await db.execute(update(OAuthCode).values(expires_at=datetime.now(UTC) - timedelta(1)))
        await db.commit()
        with pytest.raises(oauth.OAuthError) as err:
            await _exchange(db, app, code)
    assert err.value.code == "invalid_grant"


async def test_wrong_verifier_or_redirect_fails(client):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db)
        other_id = (await _register(db, name="Other")).client_id
        app_id = app.client_id
        code = await _approve(db, user, app)
        errors = []
        for kwargs in [
            {"verifier": "w" * 50},
            {"redirect": REDIRECT + "x"},
            {"client_id": other_id},
            {"client_id": "nope"},
        ]:
            with pytest.raises(oauth.OAuthError) as err:
                await _exchange(db, app, code, **{"client_id": app_id, **kwargs})
            errors.append((err.value.code, err.value.description))
        with pytest.raises(oauth.OAuthError) as err:
            await _exchange(db, app, "unknown-code", client_id=app_id)
        errors.append((err.value.code, err.value.description))
        assert set(errors) == {("invalid_grant", errors[0][1])}
        # The failed tries did not use up the code.
        token, _ = await _exchange(db, app, code, client_id=app_id)
    assert token.startswith("pdk_")


async def test_reauthorizing_same_client_leaves_one_live_token(client):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db)
        first, _ = await _exchange(db, app, await _approve(db, user, app))
        second, _ = await _exchange(db, app, await _approve(db, user, app))
    async with get_sessionmaker()() as db:
        rows = list(await db.scalars(select(ApiToken).order_by(ApiToken.created_at)))
    assert first != second
    assert len(rows) == 2
    assert rows[0].revoked_at is not None
    assert rows[1].revoked_at is None


async def test_reuse_without_stored_token_id_still_revokes(client):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db)
        code = await _approve(db, user, app)
        await _exchange(db, app, code)
        await db.execute(update(OAuthCode).values(token_id=None))
        await db.commit()
        with pytest.raises(oauth.OAuthError) as err:
            await _exchange(db, app, code)
    assert err.value.code == "invalid_grant"
    async with get_sessionmaker()() as db:
        assert (await db.scalar(select(ApiToken))).revoked_at is not None


async def test_exchange_fails_for_a_disabled_user_with_the_same_wording(client):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db)
        app_id = app.client_id
        code = await _approve(db, user, app)
        await db.execute(update(User).values(disabled_at=datetime.now(UTC)))
        await db.commit()
        with pytest.raises(oauth.OAuthError) as err:
            await _exchange(db, app, code, client_id=app_id)
        with pytest.raises(oauth.OAuthError) as unknown:
            await _exchange(db, app, "unknown-code", client_id=app_id)
    assert (err.value.code, err.value.description) == (
        unknown.value.code,
        unknown.value.description,
    )
    async with get_sessionmaker()() as db:
        assert await db.scalar(select(ApiToken)) is None


async def test_code_expiry_boundary(client, monkeypatch):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db)
        app_id = app.client_id
        code = await _approve(db, user, app)
        expires_at = (await db.scalar(select(OAuthCode))).expires_at
        monkeypatch.setattr(oauth, "_now", lambda: expires_at)
        with pytest.raises(oauth.OAuthError):
            await _exchange(db, app, code, client_id=app_id)
        monkeypatch.setattr(oauth, "_now", lambda: expires_at - timedelta(seconds=1))
        token, _ = await _exchange(db, app, code, client_id=app_id)
    assert token.startswith("pdk_")


async def test_loopback_redirect_cannot_carry_userinfo_or_fragment(client):
    async with get_sessionmaker()() as db:
        app = await _register(db, uris=["http://localhost:1234/cb"])
    for bad in (
        "http://user@localhost:5555/cb",
        "http://user:pw@localhost:5555/cb",
        "http://localhost:5555/cb#frag",
    ):
        assert not oauth.redirect_ok(bad)
        with pytest.raises(oauth.OAuthError) as err:
            _check(app, redirect_uri=bad)
        assert err.value.code == "invalid_request"


def test_control_characters_in_a_redirect_are_refused():
    for bad in (
        "https://app.example.com/c\tb",
        "https://app.example.com/cb\n",
        "https://app.exam\rple.com/cb",
        "https://app.example.com/ cb",
        "https://app.example.com/cb\x7f",
        "cursor://any\x00/oauth",
    ):
        assert not oauth.redirect_ok(bad)


async def test_challenge_with_trailing_newline_is_refused(client):
    async with get_sessionmaker()() as db:
        app = await _register(db)
    with pytest.raises(oauth.OAuthError) as err:
        _check(app, code_challenge=CHALLENGE + "\n")
    assert err.value.code == "invalid_request"


async def test_malformed_verifier_is_refused(client):
    user = await _user(client)
    async with get_sessionmaker()() as db:
        app = await _register(db)
        app_id = app.client_id
        code = await _approve(db, user, app)
        for bad in ("short", "v" * 129, VERIFIER + "\n", "v" * 49 + "!"):
            with pytest.raises(oauth.OAuthError) as err:
                await _exchange(db, app, code, verifier=bad, client_id=app_id)
            assert err.value.code == "invalid_grant"
        token, _ = await _exchange(db, app, code, client_id=app_id)
    assert token.startswith("pdk_")


async def test_token_create_without_commit_waits_for_the_caller(client):
    from app.services import tokens

    user = await _user(client)
    async with get_sessionmaker()() as db:
        await tokens.create(
            db, user, name="x", scopes=["pages:read"], expires_in_days=None, ip=None, commit=False
        )
        async with get_sessionmaker()() as other:
            assert await other.scalar(select(ApiToken)) is None
        await db.commit()
        async with get_sessionmaker()() as other:
            assert await other.scalar(select(ApiToken)) is not None
