import uuid

from app.core.security import (
    csrf_for_session,
    hash_password,
    new_secret,
    same_value,
    sha256_hex,
    verify_password,
)


def test_password_round_trip():
    hashed = hash_password("a long enough password")
    assert verify_password(hashed, "a long enough password") is True
    assert verify_password(hashed, "a different password") is False


def test_garbage_hash_does_not_crash():
    assert verify_password("not a hash", "anything") is False


def test_secrets_are_long_and_unique():
    a, b = new_secret(), new_secret()
    assert a != b
    assert len(a) >= 40


def test_sha256_is_stable():
    assert sha256_hex("abc") == sha256_hex("abc")
    assert sha256_hex("abc") != sha256_hex("abd")


def test_csrf_value_is_stable_per_session_and_differs_between_sessions():
    one, two = uuid.uuid4(), uuid.uuid4()
    assert csrf_for_session(one) == csrf_for_session(one)
    assert csrf_for_session(one) != csrf_for_session(two)


def test_same_value_compares_strings():
    assert same_value("abc", "abc") is True
    assert same_value("abc", "abd") is False
