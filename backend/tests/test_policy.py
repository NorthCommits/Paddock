import pytest

from app.core.policy import ACTIONS, ALL_SCOPES, ROLE_RANK, allowed

ROLES = ["viewer", "commenter", "editor", "owner"]

# The table from docs/SDD.md section 3.3, written out independently of the code.
EXPECTED = {
    "page.view": {"viewer", "commenter", "editor", "owner"},
    "comment.read": {"viewer", "commenter", "editor", "owner"},
    "events.read": {"viewer", "commenter", "editor", "owner"},
    "chat.write": {"viewer", "commenter", "editor", "owner"},
    "page.context": {"editor", "owner"},
    "comment.create": {"commenter", "editor", "owner"},
    "request.create": {"commenter", "editor", "owner"},
    "version.publish": {"editor", "owner"},
    "request.act": {"editor", "owner"},
    "page.update": {"owner"},
    "page.manage_sharing": {"owner"},
    "page.delete": {"owner"},
}


def test_every_action_is_covered_by_the_expected_table():
    assert set(EXPECTED) == set(ACTIONS)


@pytest.mark.parametrize("action", sorted(EXPECTED))
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix_with_every_scope(action, role):
    assert allowed(action, role, ALL_SCOPES) == (role in EXPECTED[action])


@pytest.mark.parametrize("action", sorted(EXPECTED))
@pytest.mark.parametrize("role", ROLES)
def test_a_missing_scope_always_denies(action, role):
    needed = ACTIONS[action][1]
    assert allowed(action, role, ALL_SCOPES - {needed}) is False


def test_no_role_means_no_access():
    assert allowed("page.view", None, ALL_SCOPES) is False
    assert allowed("page.view", "stranger", ALL_SCOPES) is False


def test_unknown_action_is_denied():
    assert allowed("page.explode", "owner", ALL_SCOPES) is False


def test_roles_are_ordered():
    assert ROLE_RANK["viewer"] < ROLE_RANK["commenter"] < ROLE_RANK["editor"] < ROLE_RANK["owner"]
