"""The text of the emails Paddock sends."""

from html import escape

from app.services.mailer import Message


def _page(title: str, intro: str, button: str, link: str, outro: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;background:#f6f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1d1d1b">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" style="max-width:480px;background:#ffffff;border-radius:14px;padding:32px">
<tr><td>
<p style="margin:0 0 20px;font-size:15px;font-weight:600">Paddock</p>
<h1 style="margin:0 0 12px;font-size:20px;line-height:26px">{escape(title)}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:22px;color:#4a4a45">{escape(intro)}</p>
<p style="margin:0 0 24px"><a href="{escape(link)}" style="display:inline-block;background:#2b7a4b;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px">{escape(button)}</a></p>
<p style="margin:0 0 8px;font-size:13px;line-height:19px;color:#66655e">Or paste this link into your browser:<br><span style="word-break:break-all">{escape(link)}</span></p>
<p style="margin:16px 0 0;font-size:13px;line-height:19px;color:#66655e">{escape(outro)}</p>
</td></tr></table></td></tr></table></body></html>"""


def verify_email(to: str, name: str, link: str, hours: int) -> Message:
    intro = f"Hi {name}, confirm your email address to start publishing pages on Paddock."
    outro = (
        f"This link works for {hours} hours. "
        "If you did not create a Paddock account, you can ignore this email."
    )
    text = f"{intro}\n\nConfirm your email: {link}\n\n{outro}\n"
    return Message(
        to=to,
        subject="Confirm your email for Paddock",
        text=text,
        html=_page("Confirm your email", intro, "Confirm email", link, outro),
    )


def reset_password(to: str, name: str, link: str, minutes: int) -> Message:
    intro = f"Hi {name}, we received a request to reset your Paddock password."
    outro = (
        f"This link works for {minutes} minutes and can be used once. "
        "If you did not ask for this, you can ignore this email and your password stays the same."
    )
    text = f"{intro}\n\nChoose a new password: {link}\n\n{outro}\n"
    return Message(
        to=to,
        subject="Reset your Paddock password",
        text=text,
        html=_page("Reset your password", intro, "Choose a new password", link, outro),
    )


def page_invite(to: str, inviter: str, title: str, role: str, link: str, days: int) -> Message:
    what = {
        "viewer": "view",
        "commenter": "view and comment on",
        "editor": "view, comment on and edit",
    }
    intro = f"{inviter} invited you to {what.get(role, 'view')} the page {title} on Paddock."
    outro = (
        f"This invitation works for {days} days. Sign in with {to} to accept it. "
        "If you were not expecting it, you can ignore this email."
    )
    text = f"{intro}\n\nOpen the invitation: {link}\n\n{outro}\n"
    return Message(
        to=to,
        subject=f"{inviter} shared a page with you on Paddock",
        text=text,
        html=_page("You have been invited", intro, "View invitation", link, outro),
    )
