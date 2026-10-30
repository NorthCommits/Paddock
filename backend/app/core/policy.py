"""The single place that decides who may do what.

An action needs two things at once:
  1. a token scope (agents) or a browser session (which has every scope), and
  2. a minimum role on the page.

The role part is used from milestone 3 onward, when pages exist.
"""

ALL_SCOPES = frozenset(
    {
        "pages:read",
        "pages:write",
        "comments:read",
        "comments:write",
        "requests:act",
        "events:read",
    }
)

ROLE_RANK = {"viewer": 1, "commenter": 2, "editor": 3, "owner": 4}

# action -> (minimum role, required scope)
ACTIONS = {
    "page.view": ("viewer", "pages:read"),
    "comment.read": ("viewer", "comments:read"),
    "events.read": ("viewer", "events:read"),
    "chat.write": ("viewer", "pages:read"),
    "comment.create": ("commenter", "comments:write"),
    "request.create": ("commenter", "comments:write"),
    "version.publish": ("editor", "pages:write"),
    "request.act": ("editor", "requests:act"),
    "page.update": ("owner", "pages:write"),
    "page.context": ("editor", "pages:write"),
    "page.manage_sharing": ("owner", "pages:write"),
    "page.delete": ("owner", "pages:write"),
}


def allowed(action: str, role: str | None, scopes: frozenset[str] | set[str]) -> bool:
    """True when the role is high enough and the scope is held."""
    if role not in ROLE_RANK or action not in ACTIONS:
        return False
    min_role, scope = ACTIONS[action]
    return ROLE_RANK[role] >= ROLE_RANK[min_role] and scope in scopes
