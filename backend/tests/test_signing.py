import uuid

from app.core.signing import make_content_token, read_content_token


def test_a_token_round_trips():
    page = uuid.uuid4()
    token, _ = make_content_token(page, 3, 60)
    assert read_content_token(token) == (page, 3)


def test_expired_tokens_are_refused():
    token, _ = make_content_token(uuid.uuid4(), 1, -5)
    assert read_content_token(token) is None


def test_tampering_is_detected():
    page = uuid.uuid4()
    token, _ = make_content_token(page, 1, 60)
    payload, sig = token.split(".")
    other, _ = make_content_token(page, 2, 60)
    assert read_content_token(f"{other.split('.')[0]}.{sig}") is None
    assert read_content_token(f"{payload}.{'A' * len(sig)}") is None


def test_garbage_is_refused():
    for bad in ["", "abc", "a.b", "....", "e30.e30", "🙂"]:
        assert read_content_token(bad) is None
