"""Sending email. One small interface, three implementations.

- ConsoleMailer writes the message to the log. It is the default for development.
- SmtpMailer sends through any SMTP server (Resend, Brevo, Zoho, SES, your own).
- MemoryMailer keeps messages in a list. Tests use it.
"""

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr

from app.core.config import Settings, get_settings

log = logging.getLogger("paddock.mail")


@dataclass
class Message:
    to: str
    subject: str
    text: str
    html: str | None = None


class ConsoleMailer:
    async def send(self, message: Message) -> None:
        log.info("EMAIL to=%s subject=%s\n%s", message.to, message.subject, message.text)


class MemoryMailer:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    async def send(self, message: Message) -> None:
        self.messages.append(message)


class SmtpMailer:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    async def send(self, message: Message) -> None:
        await asyncio.to_thread(self._send, message)

    def _send(self, message: Message) -> None:
        s = self.s
        mail = EmailMessage()
        mail["From"] = s.email_from
        mail["To"] = message.to
        mail["Subject"] = message.subject
        mail.set_content(message.text)
        if message.html:
            mail.add_alternative(message.html, subtype="html")

        context = ssl.create_default_context()
        if s.smtp_security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                s.smtp_host, s.smtp_port, timeout=15, context=context
            )
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
        with server:
            if s.smtp_security == "starttls":
                server.starttls(context=context)
            if s.smtp_username:
                server.login(s.smtp_username, s.smtp_password or "")
            server.send_message(mail, from_addr=parseaddr(s.email_from)[1])


_mailer = None


def get_mailer():
    global _mailer
    if _mailer is None:
        settings = get_settings()
        _mailer = SmtpMailer(settings) if settings.email_backend == "smtp" else ConsoleMailer()
    return _mailer


def set_mailer(mailer) -> None:
    """Replace the mailer. Tests use this."""
    global _mailer
    _mailer = mailer


_sending: set[asyncio.Task] = set()


def send_later(message: Message) -> None:
    """Send in the background, so the request behind the email does not wait for the mail server."""
    task = asyncio.create_task(send_quietly(message))
    _sending.add(task)
    task.add_done_callback(_sending.discard)


async def finish_sending() -> None:
    """Wait for emails started with send_later. Tests use this."""
    if _sending:
        await asyncio.gather(*list(_sending))


async def send_quietly(message: Message) -> bool:
    """Send a message. A failure is logged, never raised. True when it was sent."""
    try:
        await get_mailer().send(message)
        return True
    except Exception:
        log.exception("Could not send email to %s", message.to)
        return False
