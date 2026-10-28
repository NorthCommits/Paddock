import json

import httpx
import pytest

from paddock_cli import client as client_mod
from paddock_cli import main as cli

PAGE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "demo",
    "title": "Demo",
    "updated_at": "2026-01-01T10:00:00Z",
    "current_version": {"number": 2},
}


class Server:
    """A fake API. Routes are (method, path) -> (status, body) or a function of the request."""

    def __init__(self):
        self.routes, self.calls = {}, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        route = self.routes.get((request.method, request.url.path))
        if route is None:
            return httpx.Response(404, json={"error": {"message": "not found"}})
        if callable(route):
            return route(request)
        status, body = route
        return httpx.Response(status, json=body)


@pytest.fixture
def server(monkeypatch, tmp_path):
    srv = Server()
    monkeypatch.setenv("PADDOCK_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setenv("PADDOCK_URL", "https://site.test/api")
    monkeypatch.setenv("PADDOCK_TOKEN", "pdk_test")
    real = client_mod.Client
    monkeypatch.setattr(
        cli, "Client", lambda base, token: real(base, token, transport=httpx.MockTransport(srv))
    )
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: None)
    srv.routes[("GET", "/api/v1/me")] = (
        200,
        {"user": {"handle": "ada", "email": "a@x.io"}, "scopes": ["pages:read"]},
    )
    return srv


def run(capsys, *argv):
    code = cli.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_whoami(server, capsys):
    code, out, _ = run(capsys, "whoami")
    assert code == 0 and "@ada" in out
    assert server.calls[0].headers["authorization"] == "Bearer pdk_test"


def test_missing_credentials_is_usage_or_auth(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("PADDOCK_CONFIG", str(tmp_path / "none.json"))
    monkeypatch.delenv("PADDOCK_URL", raising=False)
    monkeypatch.delenv("PADDOCK_TOKEN", raising=False)
    code, _, err = run(capsys, "pages")
    assert code == 2 and err.startswith("error:")


def test_unauthorized_exits_3(server, capsys):
    server.routes[("GET", "/api/v1/pages")] = (401, {"error": {"message": "bad token"}})
    code, _, err = run(capsys, "pages")
    assert code == 3 and "bad token" in err


def test_pages_table(server, capsys):
    server.routes[("GET", "/api/v1/pages")] = (200, {"items": [PAGE], "next_cursor": None})
    code, out, _ = run(capsys, "pages")
    assert code == 0 and "demo" in out and "v2" in out


def test_deploy_creates_page(server, capsys, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<h1>hi</h1>")
    seen = {}

    def create(request):
        seen["body"] = request.read()
        version = {"number": 1}
        return httpx.Response(201, json={"page": PAGE, "version": version, "created": True})

    server.routes[("POST", "/api/v1/pages")] = create
    code, out, _ = run(capsys, "deploy", str(site), "--title", "Demo", "-m", "first")
    assert code == 0 and "Created" in out and "https://site.test/pages/" + PAGE["id"] in out
    assert b"index.html" in seen["body"] and b"first" in seen["body"]


def test_deploy_no_changes(server, capsys, tmp_path):
    f = tmp_path / "a.html"
    f.write_text("<p>x</p>")
    path = f"/api/v1/pages/{PAGE['id']}"
    server.routes[("GET", path)] = (200, PAGE)
    server.routes[("POST", path + "/versions")] = (
        200,
        {"page": PAGE, "version": {"number": 2}, "created": False},
    )
    code, out, _ = run(capsys, "deploy", str(f), "--page", PAGE["id"])
    assert code == 0 and "No changes" in out


def test_deploy_conflict_exits_4(server, capsys, tmp_path):
    f = tmp_path / "a.html"
    f.write_text("<p>x</p>")
    server.routes[("POST", "/api/v1/pages")] = (409, {"error": {"message": "slug taken"}})
    code, _, err = run(capsys, "deploy", str(f))
    assert code == 4 and "slug taken" in err


def test_deploy_missing_path_exits_2(server, capsys, tmp_path):
    code, _, err = run(capsys, "deploy", str(tmp_path / "nope"))
    assert code == 2 and err.startswith("error:")


def test_resolve_slug(server, capsys):
    server.routes[("GET", "/api/v1/pages")] = (200, {"items": [PAGE], "next_cursor": None})
    server.routes[("GET", f"/api/v1/pages/{PAGE['id']}/versions")] = (200, {"items": []})
    code, _, _ = run(capsys, "versions", "demo")
    assert code == 0
    assert server.calls[0].url.params["slug"] == "demo"


def test_rate_limit_is_retried(server, capsys):
    answers = iter([httpx.Response(429, headers={"retry-after": "1"}, json={}), None])

    def flaky(request):
        first = next(answers)
        return first or httpx.Response(200, json={"items": [], "next_cursor": None})

    server.routes[("GET", "/api/v1/pages")] = flaky
    code, out, _ = run(capsys, "pages")
    assert code == 0 and "Nothing to show" in out


def test_reply_posts_into_thread(server, capsys):
    item = {"page_id": PAGE["id"], "comment": {"thread_id": "t1"}}
    server.routes[("GET", "/api/v1/requests/r1")] = (200, item)
    posted = {}

    def comment(request):
        posted.update(json.loads(request.read()))
        return httpx.Response(201, json={})

    server.routes[("POST", f"/api/v1/pages/{PAGE['id']}/comments")] = comment
    code, out, _ = run(capsys, "reply", "r1", "-m", "working on it")
    assert code == 0 and posted == {"body": "working on it", "parent_id": "t1"}


def test_reply_done_needs_version(server, capsys):
    code, _, err = run(capsys, "reply", "r1", "-m", "ok", "--done")
    assert code == 2 and "--version" in err


def test_reply_done_completes(server, capsys):
    server.routes[("POST", "/api/v1/requests/r1/complete")] = (200, {"result_version": 3})
    code, out, _ = run(capsys, "reply", "r1", "-m", "ok", "--done", "--version", "3")
    assert code == 0 and "version 3" in out


def test_watch_prints_events_and_stops(server, capsys):
    event = {
        "type": "comment.created",
        "page_id": PAGE["id"],
        "created_at": "2026-01-01T10:00:05Z",
        "data": {"body": "hello", "by_agent": False},
    }
    stream = f"id: e1\nevent: comment.created\ndata: {json.dumps(event)}\n\n"
    server.routes[("GET", "/api/v1/events")] = lambda r: httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=stream.encode()
    )
    code, out, _ = run(capsys, "watch", "--count", "1")
    assert code == 0 and "comment.created" in out and "hello" in out


def test_find_base_tries_api_prefix():
    def handler(request):
        if request.url.path == "/api/v1/me":
            return httpx.Response(401, json={})
        return httpx.Response(200, text="<html>", headers={"content-type": "text/html"})

    base = client_mod.find_base("https://site.test", httpx.MockTransport(handler))
    assert base == "https://site.test/api"
