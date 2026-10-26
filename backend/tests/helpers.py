def mails_to(email: str) -> list:
    from app.services import mailer

    return [m for m in mailer.get_mailer().messages if m.to == email]


def mint_token(
    email: str = "ana@example.com",
    *,
    sub: str | None = None,
    name: str | None = None,
    verified: bool = True,
    minutes: int = 15,
    key=None,
) -> str:
    """A sign-in token like the ones Neon Auth issues, signed with the test key."""
    import time

    import jwt

    from tests.conftest import TEST_PRIVATE_KEY

    now = int(time.time())
    claims = {
        "sub": sub or f"neon-{email}",
        "email": email,
        "email_verified": verified,
        "iat": now,
        "exp": now + minutes * 60,
    }
    if name:
        claims["name"] = name
    return jwt.encode(claims, key or TEST_PRIVATE_KEY, algorithm="EdDSA", headers={"kid": "test"})


async def signup(client, email="ana@example.com", handle="ana", verify=True, name=None):
    """Create an account the way the app does: sign in with Neon, then choose a handle.

    Returns the user plus the sign-in token. csrf(data) gives the header to send.
    """
    token = mint_token(email, verified=verify, name=name)
    response = await client.post(
        "/v1/onboarding", json={"handle": handle}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201, response.text
    client.headers["Authorization"] = f"Bearer {token}"  # this client now acts as the new user
    return {"user": response.json(), "token": token, "csrf_token": token}


def csrf(data: dict) -> dict:
    """The header that signs a request in as this person. (Name kept from the cookie days.)"""
    return {"Authorization": f"Bearer {data['token']}"}


async def make_token(client, data: dict, scopes=("pages:read",), **extra):
    response = await client.post(
        "/v1/tokens",
        json={"name": "test agent", "scopes": list(scopes), **extra},
        headers=csrf(data),
    )
    assert response.status_code == 201, response.text
    return response.json()


def page_body(title="Quarterly report", files=None, **extra):
    """A JSON upload with one small HTML file."""
    files = files or [{"path": "index.html", "content": "<h1>Hello</h1>"}]
    return {"title": title, "files": files, **extra}


async def new_page(client, data, token: str | None = None, **extra) -> dict:
    """Create a page. Uses a bearer token when given, else the browser session."""
    headers = {"Authorization": f"Bearer {token}"} if token else csrf(data)
    response = await client.post("/v1/pages", json=page_body(**extra), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def auth(data: dict | None = None, token: str | None = None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else csrf(data)  # type: ignore[arg-type]
