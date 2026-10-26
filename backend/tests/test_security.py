from app.core.security import new_secret, same_value, sha256_hex


def test_secrets_are_long_and_unique():
    a, b = new_secret(), new_secret()
    assert a != b
    assert len(a) >= 40


def test_sha256_is_stable():
    assert sha256_hex("abc") == sha256_hex("abc")
    assert sha256_hex("abc") != sha256_hex("abd")


def test_same_value_compares_strings():
    assert same_value("abc", "abc") is True
    assert same_value("abc", "abd") is False
