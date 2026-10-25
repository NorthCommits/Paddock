from httpx import ASGITransport, AsyncClient

from app.main import app

from .helpers import PASSWORD, auth, make_token, signup


async def test_update_display_name(client):
    data = await signup(client)
    response = await client.patch("/v1/me", json={"display_name": "  Ana B  "}, headers=auth(data))
    assert response.status_code == 200
    assert response.json()["display_name"] == "Ana B"
    assert (await client.get("/v1/me")).json()["user"]["display_name"] == "Ana B"
    blank = await client.patch("/v1/me", json={"display_name": "  "}, headers=auth(data))
    assert blank.status_code == 422


async def test_tokens_cannot_edit_the_profile(client):
    data = await signup(client)
    token = (await make_token(client, data))["token"]
    response = await client.patch(
        "/v1/me", json={"display_name": "x"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_change_password(client):
    data = await signup(client)
    wrong = await client.post(
        "/v1/me/password",
        json={"current_password": "nope nope nope", "new_password": "a brand new phrase"},
        headers=auth(data),
    )
    assert wrong.status_code == 403
    short = await client.post(
        "/v1/me/password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=auth(data),
    )
    assert short.status_code == 422
    ok = await client.post(
        "/v1/me/password",
        json={"current_password": PASSWORD, "new_password": "a brand new phrase"},
        headers=auth(data),
    )
    assert ok.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        old = await other.post(
            "/v1/auth/login", json={"email": "ana@example.com", "password": PASSWORD}
        )
        assert old.status_code == 401
        new = await other.post(
            "/v1/auth/login", json={"email": "ana@example.com", "password": "a brand new phrase"}
        )
        assert new.status_code == 200


async def test_password_change_signs_out_other_browsers(client):
    data = await signup(client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        login = await other.post(
            "/v1/auth/login", json={"email": "ana@example.com", "password": PASSWORD}
        )
        assert (await other.get("/v1/me")).status_code == 200
        assert login.status_code == 200
        await client.post(
            "/v1/me/password",
            json={"current_password": PASSWORD, "new_password": "a brand new phrase"},
            headers=auth(data),
        )
        assert (await other.get("/v1/me")).status_code == 401
    assert (await client.get("/v1/me")).status_code == 200


async def test_list_and_revoke_sessions(client):
    data = await signup(client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await other.post("/v1/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
        rows = (await client.get("/v1/me/sessions")).json()
        assert len(rows) == 2
        assert sum(r["current"] for r in rows) == 1
        mine = next(r for r in rows if r["current"])
        theirs = next(r for r in rows if not r["current"])

        own = await client.delete(f"/v1/me/sessions/{mine['id']}", headers=auth(data))
        assert own.status_code == 422
        gone = await client.delete(f"/v1/me/sessions/{theirs['id']}", headers=auth(data))
        assert gone.status_code == 204
        assert (await other.get("/v1/me")).status_code == 401
        again = await client.delete(f"/v1/me/sessions/{theirs['id']}", headers=auth(data))
        assert again.status_code == 404


async def test_sign_out_everywhere_else(client):
    data = await signup(client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await other.post("/v1/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
        done = await client.post("/v1/me/sessions/revoke-others", headers=auth(data))
        assert done.status_code == 204
        assert (await other.get("/v1/me")).status_code == 401
    assert len((await client.get("/v1/me/sessions")).json()) == 1


async def test_cannot_revoke_someone_elses_session(client):
    data = await signup(client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as bo:
        bo_data = await signup(bo, email="bo@example.com", handle="bobby")
        bo_rows = (await bo.get("/v1/me/sessions")).json()
        response = await client.delete(f"/v1/me/sessions/{bo_rows[0]['id']}", headers=auth(data))
        assert response.status_code == 404
        assert (await bo.get("/v1/me")).status_code == 200
        assert bo_data
