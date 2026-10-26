import smtplib

from app.core.config import Settings
from app.services import mailer
from app.services.mailer import ConsoleMailer, MemoryMailer, Message, SmtpMailer


def settings(**kw):
    base = {
        "database_url": "postgresql://x/y",
        "email_backend": "smtp",
        "smtp_host": "smtp.example.com",
        "email_from": "Paddock <hello@paddock.example>",
    }
    return Settings(_env_file=None, **{**base, **kw})


class FakeSmtp:
    calls: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.calls = FakeSmtp.calls = [("connect", host, port, context is not None)]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.calls.append(("quit",))

    def starttls(self, context=None):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, mail, from_addr=None):
        self.calls.append(("send", mail, from_addr))


MESSAGE = Message(to="ana@example.com", subject="Hi", text="plain body", html="<p>html body</p>")


async def test_smtp_with_starttls_and_login(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    cfg = settings(smtp_username="user", smtp_password="pw")
    await SmtpMailer(cfg).send(MESSAGE)
    names = [c[0] for c in FakeSmtp.calls]
    assert names == ["connect", "starttls", "login", "send", "quit"]
    assert FakeSmtp.calls[0][1:3] == ("smtp.example.com", 587)
    assert FakeSmtp.calls[2][1:] == ("user", "pw")
    _, mail, from_addr = FakeSmtp.calls[3]
    assert from_addr == "hello@paddock.example"
    assert mail["To"] == "ana@example.com"
    assert mail["From"] == "Paddock <hello@paddock.example>"
    assert mail["Subject"] == "Hi"
    types = [p.get_content_type() for p in mail.iter_parts()]
    assert types == ["text/plain", "text/html"]


async def test_smtp_ssl_and_no_login(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtp)
    await SmtpMailer(settings(smtp_security="ssl", smtp_port=465)).send(MESSAGE)
    assert [c[0] for c in FakeSmtp.calls] == ["connect", "send", "quit"]
    assert FakeSmtp.calls[0][2] == 465


async def test_smtp_without_encryption(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    await SmtpMailer(settings(smtp_security="none", smtp_port=25)).send(Message("a@b.co", "s", "t"))
    assert [c[0] for c in FakeSmtp.calls] == ["connect", "send", "quit"]


async def test_send_quietly_reports_failure():
    class Broken:
        async def send(self, message):
            raise OSError("no route")

    mailer.set_mailer(Broken())
    assert await mailer.send_quietly(MESSAGE) is False
    box = MemoryMailer()
    mailer.set_mailer(box)
    assert await mailer.send_quietly(MESSAGE) is True
    assert box.messages == [MESSAGE]


async def test_console_mailer_logs_the_link():
    import logging

    seen: list[str] = []

    class Grab(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    log = logging.getLogger("paddock.mail")
    handler = Grab(level=logging.INFO)
    log.addHandler(handler)
    old = log.level
    log.setLevel(logging.INFO)
    try:
        body = "click http://x/verify-email?token=abc"
        await ConsoleMailer().send(Message("a@b.co", "Subject", body))
    finally:
        log.removeHandler(handler)
        log.setLevel(old)
    assert "verify-email?token=abc" in seen[0]
