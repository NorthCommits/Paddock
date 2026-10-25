import hashlib
from urllib.parse import urlparse

from .helpers import auth, page_body, signup

SITE = [
    {"path": "index.html", "content": "<link rel=stylesheet href=css/site.css><h1>Home</h1>"},
    {"path": "css/site.css", "content": "h1{color:green}"},
    {"path": "docs/index.html", "content": "<p>docs</p>"},
    {"path": "data.json", "content": '{"ok": true}'},
]


async def view(client, page_id, **body):
    response = await client.post(
        f"/v1/pages/{page_id}/view-url", json=body or None, headers=auth_for(client)
    )
    return response


def auth_for(client):
    return client._csrf  # set by make_site


async def make_site(client):
    data = await signup(client)
    client._csrf = auth(data)
    body = page_body(files=SITE)
    made = await client.post("/v1/pages", json=body, headers=client._csrf)
    assert made.status_code == 201, made.text
    return made.json()["page"]


def path_of(url: str) -> str:
    return urlparse(url).path


async def test_view_url_points_at_the_content_origin(client):
    page = await make_site(client)
    response = await view(client, page["id"])
    assert response.status_code == 200
    out = response.json()
    assert out["url"].startswith("http://localhost:8001/c/")
    assert out["url"].endswith("/index.html")
    assert out["expires_at"]


async def test_gateway_serves_files_with_safe_headers(client, content_client):
    page = await make_site(client)
    url = (await view(client, page["id"])).json()["url"]
    response = await content_client.get(path_of(url))
    assert response.status_code == 200
    assert "Home" in response.text
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "noindex" in response.headers["x-robots-tag"]
    assert "frame-ancestors http://localhost:3000" in response.headers["content-security-policy"]
    assert response.headers["content-length"] == str(len(response.content))

    base = path_of(url).rsplit("/", 1)[0]
    css = await content_client.get(f"{base}/css/site.css")
    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert css.text == "h1{color:green}"
    sha = hashlib.sha256(css.content).hexdigest()
    assert sha


async def test_empty_path_and_directories_fall_back_to_index(client, content_client):
    page = await make_site(client)
    url = (await view(client, page["id"])).json()["url"]
    base = path_of(url).rsplit("/", 1)[0]
    root = await content_client.get(base + "/")
    assert root.status_code == 200
    assert "Home" in root.text
    docs = await content_client.get(base + "/docs")
    assert docs.status_code == 200
    assert "docs" in docs.text


async def test_unknown_files_and_traversal_are_404(client, content_client):
    page = await make_site(client)
    url = (await view(client, page["id"])).json()["url"]
    base = path_of(url).rsplit("/", 1)[0]
    for bad in ["/nope.html", "/%2e%2e/index.html"]:
        response = await content_client.get(base + bad)
        assert response.status_code in (403, 404), (bad, response.status_code)
        assert "content-security-policy" in response.headers


async def test_bad_tokens_get_403_with_headers(content_client):
    for path in ["/c/garbage/index.html", "/c/a.b/index.html"]:
        response = await content_client.get(path)
        assert response.status_code == 403
        assert response.headers["x-content-type-options"] == "nosniff"


async def test_expired_tokens_are_refused(client, content_client):
    from app.core.signing import make_content_token

    page = await make_site(client)
    import uuid

    token, _ = make_content_token(uuid.UUID(page["id"]), 1, -10)
    assert (await content_client.get(f"/c/{token}/index.html")).status_code == 403


async def test_token_for_one_version_does_not_open_another(client, content_client):
    page = await make_site(client)
    old = (await view(client, page["id"], version=1)).json()["url"]
    new_files = [{"path": "index.html", "content": "<h1>Second</h1>"}]
    await client.post(
        f"/v1/pages/{page['id']}/versions", json={"files": new_files}, headers=auth_for(client)
    )
    latest = (await view(client, page["id"])).json()["url"]
    assert "Home" in (await content_client.get(path_of(old))).text
    assert "Second" in (await content_client.get(path_of(latest))).text
    base = path_of(old).rsplit("/", 1)[0]
    assert (await content_client.get(base + "/css/site.css")).status_code == 200
    base_new = path_of(latest).rsplit("/", 1)[0]
    assert (await content_client.get(base_new + "/css/site.css")).status_code == 404


async def test_deleted_pages_stop_serving(client, content_client):
    page = await make_site(client)
    url = (await view(client, page["id"])).json()["url"]
    assert (await content_client.get(path_of(url))).status_code == 200
    await client.delete(f"/v1/pages/{page['id']}", headers=auth_for(client))
    assert (await content_client.get(path_of(url))).status_code == 404


async def test_view_url_for_unknown_version_and_strangers(client):
    page = await make_site(client)
    assert (await view(client, page["id"], version=9)).status_code == 404
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as bo:
        data = await signup(bo, email="bo@example.com", handle="bobby")
        response = await bo.post(f"/v1/pages/{page['id']}/view-url", headers=auth(data))
        assert response.status_code == 404


async def test_health_and_unrelated_routes(content_client):
    assert (await content_client.get("/healthz")).status_code == 200
    assert (await content_client.get("/")).status_code == 404
    assert (await content_client.post("/c/x/index.html")).status_code == 405


async def test_the_main_api_has_no_content_routes(client):
    assert (await client.get("/c/abc/index.html")).status_code == 404
