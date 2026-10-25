import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app

from .helpers import auth, make_token, new_page, page_body, signup


def other_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_create_and_read_a_page(client):
    data = await signup(client)
    made = await new_page(client, data, title="Q3 report")
    page = made["page"]
    assert made["created"] is True
    assert made["version"]["number"] == 1
    assert page["slug"] == "q3-report"
    assert page["visibility"] == "private"
    assert page["owner_handle"] == "ana"
    assert page["current_version"]["entry_path"] == "index.html"

    got = await client.get(f"/v1/pages/{page['id']}")
    assert got.status_code == 200
    assert got.json()["title"] == "Q3 report"

    listing = await client.get("/v1/pages")
    assert [p["id"] for p in listing.json()["items"]] == [page["id"]]


async def test_slugs_are_unique_per_owner(client):
    data = await signup(client)
    first = await new_page(client, data, title="Notes")
    second = await new_page(client, data, title="Notes")
    assert first["page"]["slug"] == "notes"
    assert second["page"]["slug"] == "notes-2"

    body = page_body(slug="notes")
    clash = await client.post("/v1/pages", json=body, headers=auth(data))
    assert clash.status_code == 409


async def test_deleting_frees_the_slug(client):
    data = await signup(client)
    made = await new_page(client, data, title="Draft", slug="draft")
    gone = await client.delete(f"/v1/pages/{made['page']['id']}", headers=auth(data))
    assert gone.status_code == 204
    assert (await client.get(f"/v1/pages/{made['page']['id']}")).status_code == 404
    assert (await client.get("/v1/pages")).json()["items"] == []
    again = await new_page(client, data, title="Draft", slug="draft")
    assert again["page"]["slug"] == "draft"


async def test_update_title_and_slug(client):
    data = await signup(client)
    made = await new_page(client, data)
    url = f"/v1/pages/{made['page']['id']}"
    changed = await client.patch(url, json={"title": "New", "slug": "fresh"}, headers=auth(data))
    assert changed.status_code == 200
    assert (changed.json()["title"], changed.json()["slug"]) == ("New", "fresh")
    bad = await client.patch(url, json={"slug": "Bad Slug!"}, headers=auth(data))
    assert bad.status_code == 422


async def test_strangers_get_404_not_403(client):
    data = await signup(client)
    made = await new_page(client, data)
    page_id = made["page"]["id"]
    async with other_client() as bo:
        bo_data = await signup(bo, email="bo@example.com", handle="bobby")
        for method, url, body in [
            ("get", f"/v1/pages/{page_id}", None),
            ("patch", f"/v1/pages/{page_id}", {"title": "x"}),
            ("delete", f"/v1/pages/{page_id}", None),
            ("get", f"/v1/pages/{page_id}/versions", None),
            ("get", f"/v1/pages/{page_id}/versions/1", None),
            ("post", f"/v1/pages/{page_id}/versions/1/rollback", None),
            ("post", f"/v1/pages/{page_id}/view-url", None),
            ("post", f"/v1/pages/{page_id}/versions", page_body()),
        ]:
            response = await bo.request(method, url, json=body, headers=auth(bo_data))
            assert response.status_code == 404, (method, url, response.text)
        assert (await bo.get("/v1/pages")).json()["items"] == []


async def test_token_scopes_are_enforced(client):
    data = await signup(client)
    reader = (await make_token(client, data, scopes=("pages:read",)))["token"]
    writer = (await make_token(client, data, scopes=("pages:write",)))["token"]
    both = (await make_token(client, data, scopes=("pages:read", "pages:write")))["token"]

    made = await new_page(client, data)
    page_id = made["page"]["id"]

    denied = await client.post("/v1/pages", json=page_body(), headers=auth(token=reader))
    assert denied.status_code == 403
    assert (await client.get("/v1/pages", headers=auth(token=writer))).status_code == 403
    assert (await client.get("/v1/pages", headers=auth(token=reader))).status_code == 200
    one = await client.get(f"/v1/pages/{page_id}", headers=auth(token=reader))
    assert one.status_code == 200
    patch = await client.patch(
        f"/v1/pages/{page_id}", json={"title": "x"}, headers=auth(token=reader)
    )
    assert patch.status_code == 403

    created = await new_page(client, data, token=both, title="By agent")
    assert created["version"]["by_agent"] is True
    assert (await client.get("/v1/pages", headers={})).status_code == 200  # cookie session


async def test_anonymous_callers_are_refused(client):
    assert (await client.get("/v1/pages")).status_code == 401
    assert (await client.post("/v1/pages", json=page_body())).status_code in (401, 403)


async def test_browser_writes_need_csrf(client):
    await signup(client)
    response = await client.post("/v1/pages", json=page_body())
    assert response.status_code == 403


async def test_listing_pages_with_a_cursor(client):
    data = await signup(client)
    for n in range(3):
        await new_page(client, data, title=f"Page {n}")
    first = (await client.get("/v1/pages", params={"limit": 2})).json()
    assert len(first["items"]) == 2
    assert first["next_cursor"]
    rest = (
        await client.get("/v1/pages", params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert len(rest["items"]) == 1
    assert rest["next_cursor"] is None
    seen = {p["id"] for p in first["items"] + rest["items"]}
    assert len(seen) == 3
    bad = await client.get("/v1/pages", params={"cursor": "nonsense"})
    assert bad.status_code == 422


async def test_filtering_by_slug(client):
    data = await signup(client)
    await new_page(client, data, title="One", slug="one")
    await new_page(client, data, title="Two", slug="two")
    found = (await client.get("/v1/pages", params={"slug": "two"})).json()["items"]
    assert [p["slug"] for p in found] == ["two"]


async def test_validation_errors(client):
    data = await signup(client)
    for body in [
        {"files": [{"path": "index.html", "content": "x"}]},  # no title
        page_body(title="  "),
        {"title": "T", "files": []},
        page_body(files=[{"path": "../x.html", "content": "x"}]),
        page_body(files=[{"path": "run.exe", "content": "x"}]),
        page_body(files=[{"path": "index.html", "content": "!!", "encoding": "base64"}]),
    ]:
        response = await client.post("/v1/pages", json=body, headers=auth(data))
        assert response.status_code in (415, 422), (body, response.text)
        assert "error" in response.json()


async def test_concurrent_publishes_get_distinct_numbers(client):
    data = await signup(client)
    made = await new_page(client, data)
    url = f"/v1/pages/{made['page']['id']}/versions"

    async def publish(n):
        files = [{"path": "index.html", "content": f"<p>{n}</p>"}]
        return await client.post(url, json={"files": files}, headers=auth(data))

    results = await asyncio.gather(*(publish(n) for n in range(6)))
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    numbers = sorted(r.json()["version"]["number"] for r in results)
    assert numbers == [2, 3, 4, 5, 6, 7]
