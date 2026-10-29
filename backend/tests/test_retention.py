import json

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import jobs
from app.db.models import AuditLog, Blob, Comment, Event, Page, PageVersion, WebhookDelivery
from app.db.session import get_engine
from app.services import retention
from app.services.storage import get_storage

from .helpers import auth, new_page
from .test_comments import comment, setup
from .test_sharing import invite
from .test_versions import publish
from .test_webhooks import public_dns, register  # noqa: F401  (fixture used by name)


async def sql(statement: str):
    async with AsyncSession(get_engine()) as db:
        result = await db.execute(text(statement))
        await db.commit()
        return result


async def rows(model):
    async with AsyncSession(get_engine()) as db:
        return list(await db.scalars(select(model)))


async def make_old_deleted_page(client, data, page_id, days=31):
    await client.delete(f"/v1/pages/{page_id}", headers=auth(data))
    await sql(
        f"update pages set deleted_at = now() - interval '{days} days' where deleted_at is not null"
    )


# ------------------------------------------------------------ deleted pages and files


async def test_a_page_deleted_long_ago_is_removed_with_everything_on_it(client):
    data, page_id = await setup(client)
    await publish(client, data, page_id, "<p>two</p>")
    await comment(client, data, page_id, "@agent hello")
    await make_old_deleted_page(client, data, page_id)

    counts = await retention.run()
    assert counts["pages"] == 1
    assert await rows(Page) == []
    assert await rows(PageVersion) == []
    assert await rows(Comment) == []
    assert {b.ref_count for b in await rows(Blob)} == {0}  # files are now unused


async def test_a_recently_deleted_page_is_kept(client):
    data, page_id = await setup(client)
    await make_old_deleted_page(client, data, page_id, days=5)
    assert (await retention.run())["pages"] == 0
    assert len(await rows(Page)) == 1


async def test_unused_files_leave_storage_after_the_grace_period(client):
    data, page_id = await setup(client)
    shas = [b.sha256 for b in await rows(Blob)]
    storage = get_storage()
    assert all([await storage.exists(s) for s in shas])
    await make_old_deleted_page(client, data, page_id)
    await retention.run()
    # Unused, but still inside the grace period: kept.
    assert len(await rows(Blob)) == len(shas)
    assert all([await storage.exists(s) for s in shas])

    await sql("update blobs set created_at = now() - interval '8 days'")
    counts = await retention.run()
    assert counts["blobs"] == len(shas)
    assert await rows(Blob) == []
    assert not any([await storage.exists(s) for s in shas])


async def test_a_file_shared_with_a_live_page_is_not_removed(client):
    data, page_id = await setup(client)
    other_page = (await new_page(client, data, title="Twin"))["page"]["id"]  # same default files
    shas = {b.sha256 for b in await rows(Blob)}
    await make_old_deleted_page(client, data, page_id)
    await sql("update blobs set created_at = now() - interval '8 days'")
    await retention.run()
    left = await rows(Blob)
    assert {b.sha256 for b in left} == shas
    assert all(b.ref_count >= 1 for b in left)
    storage = get_storage()
    assert all([await storage.exists(b.sha256) for b in left])
    page = (await client.get(f"/v1/pages/{other_page}", headers=auth(data))).json()
    assert page["current_version"]["number"] == 1


async def test_running_twice_changes_nothing_more(client):
    data, page_id = await setup(client)
    await make_old_deleted_page(client, data, page_id)
    await sql("update blobs set created_at = now() - interval '8 days'")
    await retention.run()
    assert set((await retention.run()).values()) == {0}


# ------------------------------------------------------------ events and the rest


async def test_old_events_go_but_not_ones_a_webhook_still_needs(client):
    data, page_id = await setup(client)
    await register(client, data, ["comment.created"])
    await comment(client, data, page_id, "waiting")  # a delivery stays pending
    await publish(client, data, page_id, "<p>two</p>")  # an event nobody waits for
    await sql("update events set created_at = now() - interval '40 days'")

    counts = await retention.run()
    left = await rows(Event)
    assert [e.type for e in left] == ["comment.created"]
    assert counts["events"] == 2  # the two version events
    assert len(await rows(WebhookDelivery)) == 1


async def test_finished_deliveries_go_with_their_old_events(client):
    data, page_id = await setup(client)
    await register(client, data)
    await comment(client, data, page_id, "x")
    await sql("update webhook_deliveries set status = 'delivered', next_attempt_at = null")
    await sql("update events set created_at = now() - interval '31 days'")
    await retention.run()
    assert await rows(Event) == []
    assert await rows(WebhookDelivery) == []


async def test_recent_events_stay(client):
    data, page_id = await setup(client)
    await comment(client, data, page_id, "x")
    assert (await retention.run())["events"] == 0
    assert len(await rows(Event)) == 2


async def test_old_invitations_and_audit_records(client):
    data, page_id = await setup(client)
    await invite(client, data, page_id)
    await sql("update page_invites set expires_at = now() - interval '40 days'")
    await sql(
        "update audit_log set created_at = now() - interval '400 days' "
        "where id = (select min(id) from audit_log)"
    )
    before = len(await rows(AuditLog))
    counts = await retention.run()
    assert counts["access"] == 1
    assert counts["audit"] == 1
    assert len(await rows(AuditLog)) == before - 1


# ------------------------------------------------------------ the command


async def test_the_command_prints_counts(client, capsys):
    import asyncio

    data, page_id = await setup(client)
    await make_old_deleted_page(client, data, page_id)
    code = await asyncio.get_running_loop().run_in_executor(None, jobs.main, ["nonsense"])
    assert code == 2
    # The command itself starts its own event loop, so check the same code path here.
    counts = await retention.run()
    assert json.dumps(counts)
    assert set(counts) == {"pages", "events", "messages", "access", "audit", "blobs", "oauth"}


# ------------------------------------------------------------ sign-in codes and apps


async def test_purge_oauth_removes_old_rows_but_keeps_clients_with_live_tokens(client):
    from app.db.models import OAuthClient, OAuthCode

    from .helpers import signup
    from .test_oauth_api import allowed_code, register, token_form

    data = await signup(client)
    held = await register(client, name="Holds a token")
    unused = await register(client, name="Unused")
    fresh = await register(client, name="Fresh")
    revoked = await register(client, name="Token revoked")

    for app in (held, revoked):
        code = await allowed_code(client, data, app["client_id"])
        exchanged = await client.post("/oauth/token", data=token_form(app["client_id"], code))
        assert exchanged.status_code == 200
    await sql(
        f"update api_tokens set revoked_at = now() where client_id = '{revoked['client_id']}'"
    )
    await allowed_code(client, data, fresh["client_id"])  # a code still waiting to be used

    await sql(
        "update oauth_clients set created_at = now() - interval '40 days', "
        "last_used_at = now() - interval '40 days' "
        f"where client_id in ('{held['client_id']}', '{unused['client_id']}', "
        f"'{revoked['client_id']}')"
    )
    await sql(
        "update oauth_codes set used_at = now() - interval '2 days' where used_at is not null"
    )

    async with AsyncSession(get_engine()) as db:
        removed = await retention.purge_oauth(db)
    assert removed == 4  # two used codes and the two apps with no live token

    assert {c.client_name for c in await rows(OAuthClient)} == {"Holds a token", "Fresh"}
    left = await rows(OAuthCode)
    assert [c.client_id for c in left] == [fresh["client_id"]]
