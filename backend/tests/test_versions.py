import hashlib
import json

from .helpers import auth, make_token, new_page, page_body, signup


def files(text, extra=None):
    out = [{"path": "index.html", "content": text}]
    return out + (extra or [])


async def publish(client, data, page_id, text="<p>v2</p>", **extra):
    return await client.post(
        f"/v1/pages/{page_id}/versions",
        json={"files": files(text), **extra},
        headers=auth(data),
    )


async def test_publishing_a_new_version(client):
    data = await signup(client)
    page = (await new_page(client, data))["page"]
    response = await publish(client, data, page["id"], message="second draft")
    assert response.status_code == 201
    out = response.json()
    assert out["created"] is True
    assert out["version"]["number"] == 2
    assert out["version"]["message"] == "second draft"
    assert out["page"]["current_version"]["number"] == 2

    listing = (await client.get(f"/v1/pages/{page['id']}/versions")).json()
    assert [v["number"] for v in listing["items"]] == [2, 1]


async def test_identical_content_is_not_a_new_version(client):
    data = await signup(client)
    page = (await new_page(client, data))["page"]
    again = await publish(client, data, page["id"], text="<h1>Hello</h1>")
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["version"]["number"] == 1
    listing = (await client.get(f"/v1/pages/{page['id']}/versions")).json()
    assert len(listing["items"]) == 1


async def test_base_version_conflict(client):
    data = await signup(client)
    page = (await new_page(client, data))["page"]
    await publish(client, data, page["id"], text="<p>two</p>")
    stale = await publish(client, data, page["id"], text="<p>three</p>", base_version=1)
    assert stale.status_code == 409
    ok = await publish(client, data, page["id"], text="<p>three</p>", base_version=2)
    assert ok.status_code == 201
    assert ok.json()["version"]["number"] == 3


async def test_version_detail_lists_files(client):
    data = await signup(client)
    body = page_body(files=files("<img src='a.png'>", [{"path": "a.txt", "content": "hi"}]))
    made = await client.post("/v1/pages", json=body, headers=auth(data))
    page_id = made.json()["page"]["id"]
    detail = (await client.get(f"/v1/pages/{page_id}/versions/1")).json()
    assert [f["path"] for f in detail["files"]] == ["a.txt", "index.html"]
    expected = hashlib.sha256(b"hi").hexdigest()
    by_path = {f["path"]: f for f in detail["files"]}
    assert by_path["a.txt"]["sha256"] == expected
    assert by_path["a.txt"]["size_bytes"] == 2
    assert by_path["a.txt"]["content_type"].startswith("text/plain")
    assert (await client.get(f"/v1/pages/{page_id}/versions/9")).status_code == 404


async def test_rollback_makes_a_new_version(client):
    data = await signup(client)
    page = (await new_page(client, data))["page"]
    await publish(client, data, page["id"], text="<p>two</p>")
    url = f"/v1/pages/{page['id']}/versions/1/rollback"
    back = await client.post(url, headers=auth(data))
    assert back.status_code == 201
    out = back.json()
    assert out["version"]["number"] == 3
    assert out["version"]["rolled_back_from"] == 1
    assert out["page"]["current_version"]["number"] == 3

    detail = (await client.get(f"/v1/pages/{page['id']}/versions/3")).json()
    original = (await client.get(f"/v1/pages/{page['id']}/versions/1")).json()
    assert detail["files"] == original["files"]
    missing = await client.post(f"/v1/pages/{page['id']}/versions/42/rollback", headers=auth(data))
    assert missing.status_code == 404


async def test_rollback_to_current_content_changes_nothing(client):
    data = await signup(client)
    page = (await new_page(client, data))["page"]
    response = await client.post(f"/v1/pages/{page['id']}/versions/1/rollback", headers=auth(data))
    assert response.status_code == 200
    assert response.json()["created"] is False


async def test_multipart_upload(client):
    data = await signup(client)
    parts = [
        ("files", ("index.html", b"<h1>hi</h1>", "text/html")),
        ("files", ("css/site.css", b"body{}", "text/css")),
    ]
    response = await client.post(
        "/v1/pages", data={"title": "Multi"}, files=parts, headers=auth(data)
    )
    assert response.status_code == 201, response.text
    page_id = response.json()["page"]["id"]
    detail = (await client.get(f"/v1/pages/{page_id}/versions/1")).json()
    assert [f["path"] for f in detail["files"]] == ["css/site.css", "index.html"]


async def test_multipart_manifest_is_checked(client):
    data = await signup(client)
    html = b"<h1>hi</h1>"
    good = [{"path": "index.html", "sha256": hashlib.sha256(html).hexdigest()}]
    bad = [{"path": "index.html", "sha256": "0" * 64}]
    parts = [("files", ("index.html", html, "text/html"))]
    ok = await client.post(
        "/v1/pages",
        data={"title": "A", "manifest": json.dumps(good)},
        files=parts,
        headers=auth(data),
    )
    assert ok.status_code == 201, ok.text
    wrong = await client.post(
        "/v1/pages",
        data={"title": "B", "manifest": json.dumps(bad)},
        files=parts,
        headers=auth(data),
    )
    assert wrong.status_code == 422


async def test_base64_files_in_json(client):
    import base64

    data = await signup(client)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    body = page_body(
        files=files(
            "<img src='p.png'>",
            [{"path": "p.png", "content": base64.b64encode(png).decode(), "encoding": "base64"}],
        )
    )
    response = await client.post("/v1/pages", json=body, headers=auth(data))
    assert response.status_code == 201, response.text


async def test_oversized_upload_is_refused(client, monkeypatch):
    from app.core import config

    data = await signup(client)
    monkeypatch.setattr(config.get_settings(), "max_bundle_bytes", 50, raising=False)
    big = page_body(files=files("x" * 500))
    response = await client.post("/v1/pages", json=big, headers=auth(data))
    assert response.status_code == 413


async def test_agent_token_can_publish_and_roll_back(client):
    data = await signup(client)
    token = (await make_token(client, data, scopes=("pages:read", "pages:write")))["token"]
    page = (await new_page(client, data, token=token))["page"]
    headers = auth(token=token)
    two = await client.post(
        f"/v1/pages/{page['id']}/versions", json={"files": files("<p>2</p>")}, headers=headers
    )
    assert two.status_code == 201
    assert two.json()["version"]["by_agent"] is True
    back = await client.post(f"/v1/pages/{page['id']}/versions/1/rollback", headers=headers)
    assert back.status_code == 201


async def test_audit_trail_is_written(client):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import AuditLog
    from app.db.session import get_engine

    data = await signup(client)
    page = (await new_page(client, data))["page"]
    await publish(client, data, page["id"])
    await client.post(f"/v1/pages/{page['id']}/versions/1/rollback", headers=auth(data))
    await client.delete(f"/v1/pages/{page['id']}", headers=auth(data))
    async with AsyncSession(get_engine()) as db:
        actions = (await db.scalars(select(AuditLog.action))).all()
    for wanted in ["page.create", "version.publish", "version.rollback", "page.delete"]:
        assert wanted in actions
