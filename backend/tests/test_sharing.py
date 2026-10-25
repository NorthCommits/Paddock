import re
import uuid
from urllib.parse import urlparse

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog
from app.db.session import get_engine
from app.main import app
from app.services import sharing

from .helpers import auth, mails_to, make_token, new_page, page_body, signup

BO = {"email": "bo@example.com", "handle": "bobby"}


def other():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def raw_token(url: str) -> str:
    return re.search(r"/(?:invites|s)/([A-Za-z0-9_-]+)$", url).group(1)


async def setup(client):
    """Ana owns a page."""
    data = await signup(client)
    page = (await new_page(client, data))["page"]
    return data, page["id"]


async def invite(client, data, page_id, email=BO["email"], role="viewer"):
    r = await client.post(
        f"/v1/pages/{page_id}/invites", json={"email": email, "role": role}, headers=auth(data)
    )
    assert r.status_code == 201, r.text
    return r.json()


async def join(client, data, page_id, bo, role="viewer"):
    """Ana invites Bo, Bo signs up and accepts. Returns Bo's login data."""
    inv = await invite(client, data, page_id, role=role)
    bo_data = await signup(bo, **BO)
    r = await bo.post(f"/v1/invites/{raw_token(inv['accept_url'])}/accept", headers=auth(bo_data))
    assert r.status_code == 200, r.text
    return bo_data, r.json()


async def age_rows(table: str, column: str, days: int):
    async with AsyncSession(get_engine()) as db:
        await db.execute(text(f"update {table} set {column} = {column} - interval '{days} days'"))
        await db.commit()


# ------------------------------------------------------------ visibility


async def test_visibility_defaults_to_private_and_can_change(client):
    data, page_id = await setup(client)
    page = (await client.get(f"/v1/pages/{page_id}")).json()
    assert page["visibility"] == "private"
    assert page["role"] == "owner"
    for value in ("members", "link", "private"):
        r = await client.patch(
            f"/v1/pages/{page_id}", json={"visibility": value}, headers=auth(data)
        )
        assert r.status_code == 200
        assert r.json()["visibility"] == value
    bad = await client.patch(
        f"/v1/pages/{page_id}", json={"visibility": "public"}, headers=auth(data)
    )
    assert bad.status_code == 422


# ------------------------------------------------------------ invitations


async def test_invite_accept_and_what_a_viewer_can_do(client, outbox):
    data, page_id = await setup(client)
    inv = await invite(client, data, page_id)
    assert inv["emailed"] is True
    assert inv["accept_url"].startswith("http://localhost:3000/invites/")
    mail = mails_to("bo@example.com")[-1]
    assert inv["accept_url"] in mail.text
    assert "Ana" in mail.subject or "ana" in mail.subject.lower()
    # inviting widened a private page to members
    assert (await client.get(f"/v1/pages/{page_id}")).json()["visibility"] == "members"

    token = raw_token(inv["accept_url"])
    async with other() as bo:
        preview = await bo.get(f"/v1/invites/{token}")  # no login needed
        assert preview.status_code == 200
        assert preview.json()["page_title"] == "Quarterly report"
        assert preview.json()["role"] == "viewer"
        assert preview.json()["email"] == "bo@example.com"

        bo_data = await signup(bo, **BO)
        assert (await bo.get(f"/v1/pages/{page_id}")).status_code == 404  # not yet
        accepted = await bo.post(f"/v1/invites/{token}/accept", headers=auth(bo_data))
        assert accepted.status_code == 200
        assert accepted.json()["role"] == "viewer"

        got = await bo.get(f"/v1/pages/{page_id}")
        assert got.status_code == 200 and got.json()["role"] == "viewer"
        assert (
            await bo.post(f"/v1/pages/{page_id}/view-url", headers=auth(bo_data))
        ).status_code == 200
        assert (await bo.get(f"/v1/pages/{page_id}/versions")).status_code == 200
        listed = (await bo.get("/v1/pages")).json()["items"]
        assert [p["id"] for p in listed] == [page_id]
        assert listed[0]["role"] == "viewer"

        # but nothing that needs more than viewing
        publish = await bo.post(
            f"/v1/pages/{page_id}/versions", json=page_body(), headers=auth(bo_data)
        )
        assert publish.status_code == 403
        rename = await bo.patch(f"/v1/pages/{page_id}", json={"title": "x"}, headers=auth(bo_data))
        assert rename.status_code == 403
        assert (await bo.delete(f"/v1/pages/{page_id}", headers=auth(bo_data))).status_code == 403
        assert (await bo.get(f"/v1/pages/{page_id}/members")).status_code == 403
        invite_try = await bo.post(
            f"/v1/pages/{page_id}/invites", json={"email": "c@example.com"}, headers=auth(bo_data)
        )
        assert invite_try.status_code == 403


async def test_editor_can_publish_but_not_manage(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await join(client, data, page_id, bo, role="editor")
        files = [{"path": "index.html", "content": "<p>edited by bo</p>"}]
        publish = await bo.post(
            f"/v1/pages/{page_id}/versions", json={"files": files}, headers=auth(bo_data)
        )
        assert publish.status_code == 201
        assert publish.json()["version"]["number"] == 2
        assert publish.json()["page"]["role"] == "editor"
        assert (
            await bo.patch(f"/v1/pages/{page_id}", json={"title": "x"}, headers=auth(bo_data))
        ).status_code == 403
        assert (await bo.delete(f"/v1/pages/{page_id}", headers=auth(bo_data))).status_code == 403
        link = await bo.post(f"/v1/pages/{page_id}/links", json={}, headers=auth(bo_data))
        assert link.status_code == 403


async def test_owner_lists_updates_and_removes_members(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await join(client, data, page_id, bo)
        members = (await client.get(f"/v1/pages/{page_id}/members")).json()
        assert len(members) == 1
        assert (members[0]["handle"], members[0]["email"], members[0]["role"]) == (
            "bobby",
            "bo@example.com",
            "viewer",
        )
        uid = members[0]["user_id"]
        up = await client.patch(
            f"/v1/pages/{page_id}/members/{uid}", json={"role": "editor"}, headers=auth(data)
        )
        assert up.status_code == 204
        assert (await bo.get(f"/v1/pages/{page_id}")).json()["role"] == "editor"

        gone = await client.delete(f"/v1/pages/{page_id}/members/{uid}", headers=auth(data))
        assert gone.status_code == 204
        assert (await bo.get(f"/v1/pages/{page_id}")).status_code == 404
        assert (await bo.get("/v1/pages")).json()["items"] == []
        again = await client.delete(f"/v1/pages/{page_id}/members/{uid}", headers=auth(data))
        assert again.status_code == 404
        missing = await client.patch(
            f"/v1/pages/{page_id}/members/{uid}", json={"role": "viewer"}, headers=auth(data)
        )
        assert missing.status_code == 404


async def test_a_member_can_leave_but_not_remove_others(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await join(client, data, page_id, bo)
        me = (await bo.get("/v1/me")).json()["user"]["id"]
        owner_id = (await client.get("/v1/me")).json()["user"]["id"]
        cannot = await bo.delete(f"/v1/pages/{page_id}/members/{owner_id}", headers=auth(bo_data))
        assert cannot.status_code == 403
        left = await bo.delete(f"/v1/pages/{page_id}/members/{me}", headers=auth(bo_data))
        assert left.status_code == 204
        assert (await bo.get(f"/v1/pages/{page_id}")).status_code == 404


async def test_private_is_a_ceiling_for_members(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await join(client, data, page_id, bo)
        await client.patch(
            f"/v1/pages/{page_id}", json={"visibility": "private"}, headers=auth(data)
        )
        assert (await bo.get(f"/v1/pages/{page_id}")).status_code == 404
        assert (await bo.get("/v1/pages")).json()["items"] == []
        await client.patch(
            f"/v1/pages/{page_id}", json={"visibility": "members"}, headers=auth(data)
        )
        assert (await bo.get(f"/v1/pages/{page_id}")).status_code == 200


async def test_deleted_pages_vanish_for_members(client):
    data, page_id = await setup(client)
    async with other() as bo:
        await join(client, data, page_id, bo)
        await client.delete(f"/v1/pages/{page_id}", headers=auth(data))
        assert (await bo.get(f"/v1/pages/{page_id}")).status_code == 404
        assert (await bo.get("/v1/pages")).json()["items"] == []


# ------------------------------------------------------------ invitation security


async def test_only_the_invited_verified_address_can_accept(client):
    data, page_id = await setup(client)
    inv = await invite(client, data, page_id)
    token = raw_token(inv["accept_url"])
    async with other() as eve:
        eve_data = await signup(eve, email="eve@example.com", handle="evelyn")
        wrong = await eve.post(f"/v1/invites/{token}/accept", headers=auth(eve_data))
        assert wrong.status_code == 403
        assert "bo@example.com" in wrong.json()["error"]["message"]
        assert (await eve.get(f"/v1/pages/{page_id}")).status_code == 404
    async with other() as bo:
        bo_data = await signup(bo, verify=False, **BO)
        unverified = await bo.post(f"/v1/invites/{token}/accept", headers=auth(bo_data))
        assert unverified.status_code == 403
        assert unverified.json()["error"]["code"] == "email_not_verified"
    assert (await client.get(f"/v1/pages/{page_id}/invites")).json()[0]["email"] == "bo@example.com"


async def test_invites_work_once_and_can_expire_or_be_revoked(client):
    data, page_id = await setup(client)
    inv = await invite(client, data, page_id)
    token = raw_token(inv["accept_url"])
    async with other() as bo:
        bo_data = await signup(bo, **BO)
        assert (
            await bo.post(f"/v1/invites/{token}/accept", headers=auth(bo_data))
        ).status_code == 200
        again = await bo.post(f"/v1/invites/{token}/accept", headers=auth(bo_data))
        assert again.status_code == 404
        assert (await bo.get(f"/v1/invites/{token}")).status_code == 404

    inv2 = await invite(client, data, page_id, email="cy@example.com")
    await age_rows("page_invites", "expires_at", 8)
    async with other() as cy:
        cy_data = await signup(cy, email="cy@example.com", handle="cyrus")
        late = await cy.post(
            f"/v1/invites/{raw_token(inv2['accept_url'])}/accept", headers=auth(cy_data)
        )
        assert late.status_code == 404

    inv3 = await invite(client, data, page_id, email="cy@example.com")
    listed = (await client.get(f"/v1/pages/{page_id}/invites")).json()
    assert [i["email"] for i in listed] == ["cy@example.com"]
    revoked = await client.delete(f"/v1/pages/{page_id}/invites/{inv3['id']}", headers=auth(data))
    assert revoked.status_code == 204
    async with other() as cy:
        login = await cy.post(
            "/v1/auth/login", json={"email": "cy@example.com", "password": "correct horse battery"}
        )
        gone = await cy.post(
            f"/v1/invites/{raw_token(inv3['accept_url'])}/accept",
            headers=auth(login.json()),
        )
        assert gone.status_code == 404
    assert (
        await client.delete(f"/v1/pages/{page_id}/invites/{inv3['id']}", headers=auth(data))
    ).status_code == 404


async def test_a_new_invite_replaces_the_old_one(client):
    data, page_id = await setup(client)
    first = await invite(client, data, page_id)
    second = await invite(client, data, page_id, role="editor")
    assert len((await client.get(f"/v1/pages/{page_id}/invites")).json()) == 1
    async with other() as bo:
        bo_data = await signup(bo, **BO)
        old = await bo.post(
            f"/v1/invites/{raw_token(first['accept_url'])}/accept", headers=auth(bo_data)
        )
        assert old.status_code == 404
        new = await bo.post(
            f"/v1/invites/{raw_token(second['accept_url'])}/accept", headers=auth(bo_data)
        )
        assert new.json()["role"] == "editor"


async def test_invite_edge_cases(client):
    data, page_id = await setup(client)
    owner_email = await client.post(
        f"/v1/pages/{page_id}/invites", json={"email": "ana@example.com"}, headers=auth(data)
    )
    assert owner_email.status_code == 422
    bad_role = await client.post(
        f"/v1/pages/{page_id}/invites",
        json={"email": "x@example.com", "role": "owner"},
        headers=auth(data),
    )
    assert bad_role.status_code == 422
    async with other() as bo:
        await join(client, data, page_id, bo)
    same = await client.post(
        f"/v1/pages/{page_id}/invites",
        json={"email": "bo@example.com", "role": "viewer"},
        headers=auth(data),
    )
    assert same.status_code == 409
    # a different role for an existing member is allowed (accepting changes the role)
    upgrade = await client.post(
        f"/v1/pages/{page_id}/invites",
        json={"email": "bo@example.com", "role": "editor"},
        headers=auth(data),
    )
    assert upgrade.status_code == 201


async def test_owner_cannot_accept_and_agents_cannot_accept(client):
    data, page_id = await setup(client)
    inv = await invite(client, data, page_id)
    token = raw_token(inv["accept_url"])
    assert (await client.post(f"/v1/invites/{token}/accept")).status_code in (401, 403)
    bearer = (await make_token(client, data, scopes=("pages:read", "pages:write")))["token"]
    r = await client.post(
        f"/v1/invites/{token}/accept", headers={"Authorization": f"Bearer {bearer}"}
    )
    assert r.status_code == 403
    assert (await client.get("/v1/invites/not-a-real-token-at-all")).status_code == 404


async def test_agent_tokens_need_the_right_scope_to_share(client):
    data, page_id = await setup(client)
    reader = (await make_token(client, data, scopes=("pages:read",)))["token"]
    writer = (await make_token(client, data, scopes=("pages:read", "pages:write")))["token"]
    h = lambda t: {"Authorization": f"Bearer {t}"}  # noqa: E731
    assert (await client.get(f"/v1/pages/{page_id}/members", headers=h(reader))).status_code == 403
    assert (await client.get(f"/v1/pages/{page_id}/members", headers=h(writer))).status_code == 200
    made = await client.post(
        f"/v1/pages/{page_id}/links", json={"role": "viewer"}, headers=h(writer)
    )
    assert made.status_code == 201


# ------------------------------------------------------------ share links


async def make_link(client, data, page_id, **body):
    r = await client.post(f"/v1/pages/{page_id}/links", json=body, headers=auth(data))
    assert r.status_code == 201, r.text
    return r.json()


async def test_share_link_opens_the_page_for_anyone(client, content_client):
    data, page_id = await setup(client)
    link = await make_link(client, data, page_id, role="viewer")
    assert link["url"].startswith("http://localhost:3000/s/")
    assert (await client.get(f"/v1/pages/{page_id}")).json()["visibility"] == "link"
    token = raw_token(link["url"])

    async with other() as anon:  # not signed in
        shared = await anon.get(f"/v1/shared/{token}")
        assert shared.status_code == 200
        body = shared.json()
        assert body["title"] == "Quarterly report"
        assert body["role"] == "viewer"
        assert body["owner_handle"] == "ana"
        assert body["version_number"] == 1
        assert "slug" not in body and "owner_id" not in body

        view = await anon.post(f"/v1/shared/{token}/view-url")
        assert view.status_code == 200
        served = await content_client.get(urlparse(view.json()["url"]).path)
        assert served.status_code == 200 and "Hello" in served.text
        assert "noindex" in served.headers["x-robots-tag"]

        # a link is not an account: nothing else opens
        assert (await anon.get(f"/v1/pages/{page_id}")).status_code == 401


async def test_commenter_links_and_listing(client):
    data, page_id = await setup(client)
    a = await make_link(client, data, page_id, role="commenter", expires_in_days=7)
    b = await make_link(client, data, page_id)
    listed = (await client.get(f"/v1/pages/{page_id}/links")).json()
    assert {x["id"] for x in listed} == {a["id"], b["id"]}
    assert all("url" not in x and "token" not in x for x in listed)
    async with other() as anon:
        assert (await anon.get(f"/v1/shared/{raw_token(a['url'])}")).json()["role"] == "commenter"
    bad = await client.post(
        f"/v1/pages/{page_id}/links", json={"role": "editor"}, headers=auth(data)
    )
    assert bad.status_code == 422


async def test_link_stops_when_revoked_expired_or_narrowed(client):
    data, page_id = await setup(client)
    revoked = await make_link(client, data, page_id)
    expiring = await make_link(client, data, page_id, expires_in_days=1)
    steady = await make_link(client, data, page_id)

    async with other() as anon:
        ok = lambda l: anon.get(f"/v1/shared/{raw_token(l['url'])}")  # noqa: E731
        assert (await ok(revoked)).status_code == 200

        gone = await client.delete(f"/v1/pages/{page_id}/links/{revoked['id']}", headers=auth(data))
        assert gone.status_code == 204
        assert (await ok(revoked)).status_code == 404
        assert (
            await client.delete(f"/v1/pages/{page_id}/links/{revoked['id']}", headers=auth(data))
        ).status_code == 404

        await age_rows("share_links", "expires_at", 2)
        assert (await ok(expiring)).status_code == 404
        assert [
            x["expired"]
            for x in (await client.get(f"/v1/pages/{page_id}/links")).json()
            if x["id"] == expiring["id"]
        ] == [True]

        assert (await ok(steady)).status_code == 200
        await client.patch(
            f"/v1/pages/{page_id}", json={"visibility": "members"}, headers=auth(data)
        )
        assert (await ok(steady)).status_code == 404
        assert (
            await anon.post(f"/v1/shared/{raw_token(steady['url'])}/view-url")
        ).status_code == 404
        await client.patch(f"/v1/pages/{page_id}", json={"visibility": "link"}, headers=auth(data))
        assert (await ok(steady)).status_code == 200  # switched back on

        await client.delete(f"/v1/pages/{page_id}", headers=auth(data))
        assert (await ok(steady)).status_code == 404


async def test_bad_link_tokens(client):
    for token in ("nothing", "x" * 43, str(uuid.uuid4())):
        async with other() as anon:
            r = await anon.get(f"/v1/shared/{token}")
            assert r.status_code == 404
            assert r.json()["error"]["code"] == "not_found"


async def test_limits(client, monkeypatch):
    data, page_id = await setup(client)
    monkeypatch.setattr(sharing, "MAX_LINKS", 2)
    monkeypatch.setattr(sharing, "MAX_INVITES", 2)
    await make_link(client, data, page_id)
    await make_link(client, data, page_id)
    third = await client.post(f"/v1/pages/{page_id}/links", json={}, headers=auth(data))
    assert third.status_code == 409
    await invite(client, data, page_id, email="a1@example.com")
    await invite(client, data, page_id, email="a2@example.com")
    over = await client.post(
        f"/v1/pages/{page_id}/invites", json={"email": "a3@example.com"}, headers=auth(data)
    )
    assert over.status_code == 409


async def test_strangers_cannot_manage_sharing(client):
    data, page_id = await setup(client)
    async with other() as eve:
        eve_data = await signup(eve, email="eve@example.com", handle="evelyn")
        for method, url, body in [
            ("get", f"/v1/pages/{page_id}/members", None),
            ("get", f"/v1/pages/{page_id}/invites", None),
            ("get", f"/v1/pages/{page_id}/links", None),
            ("post", f"/v1/pages/{page_id}/invites", {"email": "a@example.com"}),
            ("post", f"/v1/pages/{page_id}/links", {}),
            ("delete", f"/v1/pages/{page_id}/members/{uuid.uuid4()}", None),
        ]:
            r = await eve.request(method, url, json=body, headers=auth(eve_data))
            assert r.status_code == 404, (method, url, r.text)


async def test_sharing_is_audited(client):
    data, page_id = await setup(client)
    async with other() as bo:
        await join(client, data, page_id, bo)
    await make_link(client, data, page_id)
    async with AsyncSession(get_engine()) as db:
        actions = set((await db.scalars(select(AuditLog.action))).all())
    assert {"invite.create", "member.add", "link.create"} <= actions
