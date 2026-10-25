import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.bundles import IncomingFile, check_bundle, fingerprint, normalise_path

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def settings(**kw):
    return Settings(database_url="postgresql://x/y", **kw)


def f(path, data=b"<h1>x</h1>", sha=None):
    return IncomingFile(path, data if isinstance(data, bytes) else data.encode(), sha)


def refuses(status, files, entry=None, **kw):
    with pytest.raises(AppError) as err:
        check_bundle(files, entry, settings(**kw))
    assert err.value.status == status, err.value.message
    return err.value


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("index.html", "index.html"),
        ("Assets/App.JS", "assets/app.js"),
        ("./a/b.css", "a/b.css"),
        ("a\\b.css", "a/b.css"),
        ("  x.txt ", "x.txt"),
    ],
)
def test_paths_are_cleaned(raw, clean):
    assert normalise_path(raw) == clean


@pytest.mark.parametrize(
    "raw",
    ["", "/etc/passwd", "../x.html", "a/../../x.html", "a//b.html", "a/./b.html", "a b.html",
     "a/b?.html", "ü.html", "x" * 250 + ".html", "a/", ".."],
)  # fmt: skip
def test_bad_paths_are_refused(raw):
    with pytest.raises(AppError) as err:
        normalise_path(raw)
    assert err.value.status == 422


def test_a_normal_bundle_passes():
    files, entry = check_bundle([f("index.html"), f("img/logo.png", PNG)], None, settings())
    assert entry == "index.html"
    assert [x.path for x in files] == ["img/logo.png", "index.html"]
    assert files[1].content_type.startswith("text/html")


def test_a_single_html_file_becomes_index():
    files, entry = check_bundle([f("My-Report.HTML")], None, settings())
    assert entry == "index.html"
    assert files[0].path == "index.html"


def test_entry_must_exist_and_be_html():
    refuses(422, [f("a.html")], "index.html" if False else "missing.html")
    refuses(422, [f("index.html"), f("style.css", "a{}")], "style.css")


def test_custom_entry():
    _, entry = check_bundle([f("home.html"), f("index.html")], "home.html", settings())
    assert entry == "home.html"


def test_empty_bundle_and_duplicates():
    refuses(422, [])
    refuses(422, [f("index.html"), f("INDEX.html")])


def test_limits():
    refuses(413, [f("index.html"), f("a.txt", "x"), f("b.txt", "x")], max_files=2)
    refuses(413, [f("index.html", b"x" * 11)], max_file_bytes=10)
    refuses(413, [f("index.html", b"x" * 8), f("a.txt", b"x" * 8)], max_bundle_bytes=10)


def test_unknown_types_are_refused():
    refuses(415, [f("index.html"), f("run.exe", b"MZ")])
    refuses(415, [f("index.html"), f("README", b"hi")])
    refuses(415, [f("index.html"), f("a.php", b"<?php")])


@pytest.mark.parametrize(
    ("path", "data"),
    [
        ("a.png", b"not a png"),
        ("a.jpg", PNG),
        ("a.gif", PNG),
        ("a.webp", b"RIFF0000WAVE"),
        ("a.woff2", b"wOFF"),
        ("a.mp4", b"\x00" * 20),
        ("a.json", b"{not json"),
        ("a.svg", b"<html></html>"),
        ("a.css", b"\xff\xfe\x00"),
        ("a.txt", b"hello\x00world"),
    ],
)
def test_content_must_match_the_extension(path, data):
    refuses(415, [f("index.html"), f(path, data)])


def test_good_binary_and_text_files_pass():
    check_bundle(
        [
            f("index.html"),
            f("a.png", PNG),
            f("a.jpg", b"\xff\xd8\xff\xe0" + b"0" * 10),
            f("a.gif", b"GIF89a" + b"0" * 10),
            f("a.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 "),
            f("a.svg", "<svg xmlns='http://www.w3.org/2000/svg'></svg>"),
            f("a.json", '{"a": 1}'),
            f("a.mp4", b"\x00\x00\x00\x18ftypmp42"),
        ],
        None,
        settings(),
    )


def test_checksums_are_verified():
    import hashlib

    good = hashlib.sha256(b"<h1>x</h1>").hexdigest()
    check_bundle([f("index.html", sha=good.upper())], None, settings())
    refuses(422, [f("index.html", sha="0" * 64)])


def test_fingerprint_ignores_order_but_not_content_or_entry():
    a = fingerprint([("a", "1"), ("b", "2")], "a")
    assert a == fingerprint([("b", "2"), ("a", "1")], "a")
    assert a != fingerprint([("a", "1"), ("b", "3")], "a")
    assert a != fingerprint([("a", "1"), ("b", "2")], "b")
