"""The text of the emails Paddock sends."""

from html import escape

from app.services.mailer import Message


def _page(title: str, intro: str, button: str, link: str, outro: str, extra: str = "") -> str:
    return f"""<!doctype html>
<html><body style="margin:0;background:#f6f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1d1d1b">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" style="max-width:480px;background:#ffffff;border-radius:14px;padding:32px">
<tr><td>
<p style="margin:0 0 20px;font-size:15px;font-weight:600">Paddock</p>
<h1 style="margin:0 0 12px;font-size:20px;line-height:26px">{escape(title)}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:22px;color:#4a4a45">{escape(intro)}</p>
{extra}<p style="margin:0 0 24px"><a href="{escape(link)}" style="display:inline-block;background:#2b7a4b;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px">{escape(button)}</a></p>
<p style="margin:0 0 8px;font-size:13px;line-height:19px;color:#66655e">Or paste this link into your browser:<br><span style="word-break:break-all">{escape(link)}</span></p>
<p style="margin:16px 0 0;font-size:13px;line-height:19px;color:#66655e">{escape(outro)}</p>
</td></tr></table></td></tr></table></body></html>"""


_WHAT_YOU_CAN_DO = {
    "viewer": "You can read it.",
    "commenter": "You can read it and leave comments.",
    "editor": "You can read it, comment and edit.",
}


def _one_line(value: str, limit: int) -> str:
    """Collapse whitespace so a name or title can never break a header, and keep it short."""
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


def page_invite(
    to: str,
    inviter: str,
    title: str,
    role: str,
    link: str,
    days: int,
    message: str | None = None,
    reply_to: str | None = None,
) -> Message:
    who = _one_line(inviter, 60)
    page = _one_line(title, 80)
    can = _WHAT_YOU_CAN_DO.get(role, _WHAT_YOU_CAN_DO["viewer"])
    intro = (
        f"{who} would like you to take a look at {page} on Paddock, "
        f"a shared place where people and their AI assistants keep pages up to date. {can}"
    )
    outro = (
        f"This invitation is for {to} and works for {days} days. Sign in with that address "
        f"to accept it. You can reply to this email to reach {who}. If you were not "
        "expecting it, you can safely ignore this message."
    )
    quote = ""
    text_quote = ""
    if message:
        quote = (
            f'<p style="margin:0 0 6px;font-size:13px;color:#66655e">{escape(who)} wrote:</p>'
            '<p style="margin:0 0 24px;padding:12px 16px;border-left:3px solid #2b7a4b;'
            'background:#f6f5f0;font-size:15px;line-height:22px;white-space:pre-wrap">'
            f"{escape(message)}</p>"
        )
        text_quote = f"{who} wrote:\n{message}\n\n"
    text = f"Hello,\n\n{intro}\n\n{text_quote}Open the page: {link}\n\n{outro}\n"
    return Message(
        to=to,
        subject=f"{who} invited you to {page} on Paddock",
        text=text,
        html=_page(f"{who} invited you", intro, "Open the page", link, outro, extra=quote),
        reply_to=reply_to,
    )


def agent_request(
    to: str, who: str, title: str, excerpt: str, quote: str | None, link: str
) -> Message:
    about = f" about \u201c{quote}\u201d" if quote else ""
    intro = f"{who} asked for an agent to change {title}{about}: \u201c{excerpt}\u201d"
    outro = (
        "Your agent will not touch it unless you say yes. Open the page and choose Let my agent do "
        "it. If a colleague says yes first, you will see that instead. You can turn these emails "
        "off in Settings, Profile."
    )
    text = f"{intro}\n\nOpen the page: {link}\n\n{outro}\n"
    return Message(
        to=to,
        subject=f"{who} needs a yes for an agent: {title}",
        text=text,
        html=_page("A request needs your yes", intro, "Open the page", link, outro),
    )
