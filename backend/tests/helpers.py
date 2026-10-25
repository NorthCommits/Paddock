PASSWORD = "correct horse battery"


async def signup(client, email="ana@example.com", handle="ana", password=PASSWORD):
    response = await client.post(
        "/v1/auth/signup",
        json={"email": email, "password": password, "handle": handle},
    )
    assert response.status_code == 201, response.text
    return response.json()


def csrf(data: dict) -> dict:
    return {"X-CSRF-Token": data["csrf_token"]}


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
