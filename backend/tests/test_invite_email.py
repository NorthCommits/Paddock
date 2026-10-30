import smtplib

from app.core.config import Settings
from app.services import emails
from app.services.mailer import Message, SmtpMailer

from .helpers import auth, mails_to
from .test_mailer import FakeSmtp
from .test_sharing import invite, setup

LINK = "https://paddock.example/invites/abc123"


def build(**kw):
    args = {
        "to": "bo@example.com",
        "inviter": "Ana Rivera",
        "title": "Roadmap",
        "role": "commenter",
        "link": LINK,
        "days": 7,
        **kw,
    }
    return emails.page_invite(**args)


def test_the_invitation_is_warm_and_complete():
    mail = build(message="So glad to share this with you.", reply_to="ana@example.com")
    assert mail.subject == "Ana Rivera invited you to Roadmap on Paddock"
    assert mail.reply_to == "ana@example.com"
    for body in (mail.text, mail.html):
        assert "Ana Rivera" in body
        assert "Roadmap" in body
        assert LINK in body
        assert "7 days" in body
        assert "bo@example.com" in body
        assert "So glad to share this with you." in body
    assert "read it and leave comments" in mail.text
    assert "reply to this email" in mail.text.lower()


def test_the_role_is_explained_in_plain_words():
    assert "You can read it." in build(role="viewer").text
    assert "read it and leave comments" in build(role="commenter").text
    assert "read it, comment and edit" in build(role="editor").text


def test_without_a_personal_message_there_is_no_message_block():
    mail = build()
    assert mail.reply_to is None
    assert "wrote:" not in mail.text
    assert "wrote:" not in mail.html


def test_a_personal_message_cannot_inject_markup():
    mail = build(message="<script>alert(1)</script> hello")
    assert "<script>" not in mail.html
    assert "&lt;script&gt;" in mail.html


def test_the_subject_stays_on_one_line_and_short():
    mail = build(title="Line one\nBcc: evil@example.com", inviter="Ana\r\nRivera")
    assert "\n" not in mail.subject and "\r" not in mail.subject
    assert len(build(title="x" * 500).subject) < 140


async def test_smtp_sends_a_reply_to_header_only_when_given(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    cfg = Settings(
        _env_file=None,
        database_url="postgresql://x/y",
        email_backend="smtp",
        smtp_host="smtp.example.com",
        email_from="Paddock <hello@paddock.example>",
    )
    await SmtpMailer(cfg).send(Message(to="a@b.co", subject="s", text="t", reply_to="ana@x.co"))
    assert FakeSmtp.calls[-2][1]["Reply-To"] == "ana@x.co"
    await SmtpMailer(cfg).send(Message(to="a@b.co", subject="s", text="t"))
    assert FakeSmtp.calls[-2][1]["Reply-To"] is None


async def post_invite(client, data, page_id, **body):
    return await client.post(
        f"/v1/pages/{page_id}/invites",
        json={"email": "bo@example.com", **body},
        headers=auth(data),
    )


async def test_the_email_carries_the_message_and_replies_go_to_the_inviter(client):
    data, page_id = await setup(client)
    r = await post_invite(client, data, page_id, message="  Looking forward to your thoughts.  ")
    assert r.status_code == 201, r.text
    mail = mails_to("bo@example.com")[-1]
    assert "Looking forward to your thoughts." in mail.text
    assert mail.reply_to == "ana@example.com"
    assert r.json()["accept_url"] in mail.text


async def test_a_blank_message_is_ignored(client):
    data, page_id = await setup(client)
    r = await post_invite(client, data, page_id, message="   ")
    assert r.status_code == 201
    assert "wrote:" not in mails_to("bo@example.com")[-1].text


async def test_a_personal_message_has_a_length_limit_and_no_links(client):
    data, page_id = await setup(client)
    too_long = await post_invite(client, data, page_id, message="x" * 501)
    assert too_long.status_code == 422
    for bad in ("see https://evil.example now", "go to www.evil.example", "evil.example/login"):
        r = await post_invite(client, data, page_id, message=bad)
        assert r.status_code == 422, bad
    assert mails_to("bo@example.com") == []


async def test_sending_again_emails_a_fresh_link_and_retires_the_old_one(client):
    data, page_id = await setup(client)
    first = await invite(client, data, page_id)
    second = await invite(client, data, page_id)
    assert first["accept_url"] != second["accept_url"]
    assert len(mails_to("bo@example.com")) == 2
