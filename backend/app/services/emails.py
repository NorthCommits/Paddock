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


def agent_request(
    to: str, who: str, title: str, excerpt: str, quote: str | None, link: str
) -> Message:
    about = f" about \u201c{quote}\u201d" if quote else ""
    intro = f"{who} asked your agent to change {title}{about}: \u201c{excerpt}\u201d"
    outro = (
        f"Nothing happens until your agent looks. Open Claude, ChatGPT, Codex or whichever agent "
        f"you connected and say: Check Paddock for open requests on {title} and handle them. "
        "You can turn these emails off in Settings, Profile."
    )
    text = f"{intro}\n\nOpen the page: {link}\n\n{outro}\n"
    return Message(
        to=to,
        subject=f"{who} is waiting on your agent: {title}",
        text=text,
        html=_page("A request is waiting for your agent", intro, "Open the page", link, outro),
    )
