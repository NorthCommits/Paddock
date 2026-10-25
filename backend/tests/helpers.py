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
