"""The `paddock` command. Every command is one or two API calls (see docs/SDD.md section 9)."""

import argparse
import getpass
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

from . import __version__, bundle, config
from .client import Client, dumps, find_base
from .errors import AUTH, USAGE, CliError

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def say(text: str = "") -> None:
    print(text, flush=True)


def table(rows: list[list[str]], headers: list[str]) -> None:
    if not rows:
        say("Nothing to show.")
        return
    widths = [max(len(str(r[i])) for r in [headers, *rows]) for i in range(len(headers))]
    for row in [headers, *rows]:
        say("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)).rstrip())


def short(text: str, n: int = 70) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "..."


def page_url(client: Client, page: dict) -> str | None:
    return f"{client.site}/pages/{page['id']}" if client.site else None


def resolve_page(client: Client, ref: str) -> dict:
    """A page can be named by its id or by its slug."""
    if UUID.match(ref):
        return client.get(f"/v1/pages/{ref}")
    found = client.get("/v1/pages", slug=ref, limit=1)["items"]
    if not found:
        raise CliError(f'No page "{ref}". Run: paddock pages')
    return found[0]


# ---------------------------------------------------------------- account


def cmd_login(args) -> None:
    saved = config.load()
    url = args.url or os.environ.get("PADDOCK_URL") or saved.get("url")
    if not url:
        url = input("Server address (for example https://paddock-project.vercel.app): ").strip()
    token = os.environ.get("PADDOCK_TOKEN")
    if not token:
        token = sys.stdin.readline().strip() if args.stdin else getpass.getpass("Token (pdk_...): ")
    if not token.startswith("pdk_"):
        raise CliError("That does not look like a Paddock token. Tokens start with pdk_", USAGE)
    base = find_base(url)
    me = Client(base, token).get("/v1/me")
    path = config.save(base, token)
    say(f"Signed in as @{me['user']['handle']}. Scopes: {', '.join(me['scopes'])}")
    say(f"Saved to {path}")


def cmd_logout(args) -> None:
    say("Signed out. The saved token was removed." if config.forget() else "Nothing was saved.")


def cmd_whoami(args, client: Client) -> None:
    me = client.get("/v1/me")
    if args.json:
        say(dumps(me))
    else:
        say(f"@{me['user']['handle']}  {me['user']['email']}")
        say(f"server: {client.base}")
        say(f"scopes: {', '.join(me['scopes'])}")


# ---------------------------------------------------------------- pages


def cmd_deploy(args, client: Client) -> None:
    files = bundle.collect(args.path)
    parts, manifest = bundle.multipart(files)
    fields = {"message": args.message, "manifest": manifest, "entry_path": args.entry}
    if args.page:
        page = resolve_page(client, args.page)
        result = client.post(
            f"/v1/pages/{page['id']}/versions",
            data={k: v for k, v in fields.items() if v},
            files=parts,
        )
    else:
        title = args.title or Path(args.path).resolve().stem
        fields |= {"title": title, "slug": args.slug}
        result = client.post("/v1/pages", data={k: v for k, v in fields.items() if v}, files=parts)
    page, version = result["page"], result["version"]
    url = page_url(client, page)
    if args.json:
        say(dumps({**result, "url": url}))
        return
    if not result["created"]:
        say(f"No changes. Version {version['number']} is still current.")
    elif version["number"] == 1:
        say(f'Created "{page["title"]}" with version 1.')
    else:
        say(f'Published version {version["number"]} of "{page["title"]}".')
    say(f"  page:    {page['id']}  ({page['slug']})")
    say(f"  version: {version['number']}")
    if url:
        say(f"  url:     {url}")


def cmd_pages(args, client: Client) -> None:
    items, cursor = [], None
    while True:
        res = client.get("/v1/pages", limit=100, cursor=cursor)
        items += res["items"]
        cursor = res["next_cursor"]
        if not cursor:
            break
    if args.json:
        say(dumps(items))
        return
    table(
        [
            [
                p["id"],
                p["slug"],
                short(p["title"], 40),
                f"v{p['current_version']['number']}" if p["current_version"] else "-",
                p["updated_at"][:16].replace("T", " "),
            ]
            for p in items
        ],
        ["ID", "SLUG", "TITLE", "VERSION", "UPDATED"],
    )


def cmd_versions(args, client: Client) -> None:
    page = resolve_page(client, args.page)
    items = client.get(f"/v1/pages/{page['id']}/versions", limit=100)["items"]
    if args.json:
        say(dumps(items))
        return
    table(
        [
            [
                f"v{v['number']}",
                short(v["message"] or "", 40),
                "agent" if v["by_agent"] else "person",
                str(v["file_count"]),
                v["created_at"][:16].replace("T", " "),
            ]
            for v in items
        ],
        ["VERSION", "NOTE", "BY", "FILES", "WHEN"],
    )


def cmd_rollback(args, client: Client) -> None:
    page = resolve_page(client, args.page)
    result = client.post(f"/v1/pages/{page['id']}/versions/{args.version}/rollback")
    if args.json:
        say(dumps(result))
    elif result["created"]:
        say(f"Restored version {args.version} as version {result['version']['number']}.")
    else:
        say(f"Version {args.version} is already the current content.")


# ---------------------------------------------------------------- comments and requests


def cmd_comments(args, client: Client) -> None:
    page = resolve_page(client, args.page)
    threads = client.get(f"/v1/pages/{page['id']}/comments", status=args.status)["items"]
    if args.json:
        say(dumps(threads))
        return
    if not threads:
        say("No comments.")
    for t in threads:
        flag = " [resolved]" if t["resolved_at"] else ""
        say(f"{t['id']}{flag}")
        for c in [t, *t["replies"]]:
            who = "(deleted)" if c["deleted"] else f"@{c['author']['handle']}"
            chip = f"  <{c['request']['status']}>" if c.get("request") else ""
            indent = "  " if c is t else "    "
            say(f"{indent}{who}: {short(c['body'], 100)}{chip}")


def cmd_requests(args, client: Client) -> None:
    page_id = resolve_page(client, args.page)["id"] if args.page else None
    items = client.get("/v1/requests", status=args.status, page_id=page_id, limit=args.limit)[
        "items"
    ]
    if args.json:
        say(dumps(items))
        return
    table(
        [
            [
                i["id"],
                i["status"],
                short(i["page_slug"], 24),
                f"v{i['base_version']}" if i["base_version"] else "-",
                f"@{i['comment']['author']['handle']}: {short(i['comment']['body'], 50)}",
            ]
            for i in items
        ],
        ["ID", "STATUS", "PAGE", "ON", "REQUEST"],
    )


def cmd_claim(args, client: Client) -> None:
    body = {"minutes": args.minutes} if args.minutes else {}
    item = client.post(f"/v1/requests/{args.request}/claim", body)
    if args.json:
        say(dumps(item))
        return
    say(f"Claimed until {item['claim_expires_at'][11:16]} UTC.")
    say(f"page:    {item['page_slug']}  ({item['page_id']})")
    say(f"request: {item['comment']['body']}")


def cmd_reply(args, client: Client) -> None:
    if args.done and not args.version:
        raise CliError("--done needs --version N, the version you published", USAGE)
    if args.done:
        item = client.post(
            f"/v1/requests/{args.request}/complete",
            {"result_version": args.version, "reply": args.message},
        )
        say(f"Done. Request completed with version {item['result_version']}.")
        return
    item = client.get(f"/v1/requests/{args.request}")
    client.post(
        f"/v1/pages/{item['page_id']}/comments",
        {"body": args.message, "parent_id": item["comment"]["thread_id"]},
    )
    say("Reply posted.")


# ---------------------------------------------------------------- watch


def describe(event: dict) -> str:
    data, kind = event.get("data", {}), event["type"]
    if kind == "comment.created":
        who = "agent" if data.get("by_agent") else "person"
        return f"{who}: {short(data.get('body', ''))}"
    if kind.startswith("request."):
        extra = f" v{data['result_version']}" if "result_version" in data else ""
        body = f" {short(data['body'])}" if data.get("body") else ""
        return f"{data.get('request_id', '')}{extra}{body}"
    if kind.startswith("version."):
        return f"v{data.get('version')} {short(data.get('message') or '', 40)}".strip()
    return dumps(data) if data else ""


def cmd_watch(args, client: Client) -> None:
    path = "/v1/events"
    if args.page:
        path = f"/v1/pages/{resolve_page(client, args.page)['id']}/events"
    last, wait, seen = None, 1, 0
    try:
        while True:
            try:
                for event_id, name, data in client.events(path, last):
                    wait = 1
                    if name == "resync":
                        say(dumps({"type": "resync"}) if args.json else "resync (refetch)")
                        continue
                    last = event_id
                    if args.json:
                        say(data)
                    else:
                        e = json.loads(data)
                        page = (e["page_id"] or "")[:8]
                        say(f"{e['created_at'][11:19]}  {e['type']:<18} {page:<8}  {describe(e)}")
                    seen += 1
                    if args.count and seen >= args.count:
                        return
            except CliError as err:
                if err.code == AUTH:
                    raise
                print(f"watch: {err.message}. Reconnecting.", file=sys.stderr, flush=True)
            except httpx.HTTPError as err:
                print(f"watch: {err}. Reconnecting.", file=sys.stderr, flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 30)
    except KeyboardInterrupt:
        return


# ---------------------------------------------------------------- command line


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print JSON instead of text")
    common.add_argument("--url", help="server address, overrides PADDOCK_URL and the saved one")

    parser = argparse.ArgumentParser(prog="paddock", description="Paddock command line tool")
    parser.add_argument("-V", "--version", action="version", version=f"paddock {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    def add(name, help_, handler, needs_client=True):
        p = sub.add_parser(name, help=help_, description=help_, parents=[common])
        p.set_defaults(handler=handler, needs_client=needs_client)
        return p

    p = add("login", "store a token and the server address", cmd_login, False)
    p.add_argument("--stdin", action="store_true", help="read the token from standard input")
    add("logout", "remove the saved token", cmd_logout, False)
    add("whoami", "show who the token belongs to", cmd_whoami)

    p = add("deploy", "create a page or publish a new version", cmd_deploy)
    p.add_argument("path", help="an .html file or a folder with index.html")
    p.add_argument("--page", help="id or slug of the page to update (omit to create a new page)")
    p.add_argument("-m", "--message", help="note for this version")
    p.add_argument("--title", help="title for a new page (default: the file or folder name)")
    p.add_argument("--slug", help="address for a new page")
    p.add_argument("--entry", help="the file to open first, if not index.html")

    add("pages", "list pages", cmd_pages)
    add("versions", "list the versions of a page", cmd_versions).add_argument("page")
    p = add("rollback", "publish an earlier version again", cmd_rollback)
    p.add_argument("page")
    p.add_argument("version", type=int)
    p = add("comments", "show comment threads", cmd_comments)
    p.add_argument("page")
    p.add_argument("--status", choices=["open", "resolved"])
    p = add("requests", "list requests from @agent mentions", cmd_requests)
    p.add_argument("--status", choices=["open", "claimed", "done", "dismissed"])
    p.add_argument("--page", help="only this page")
    p.add_argument("--limit", type=int, default=50)
    p = add("claim", "claim a request so no other agent takes it", cmd_claim)
    p.add_argument("request")
    p.add_argument("--minutes", type=int, help="how long to hold it (default 10, up to 60)")
    p = add("reply", "reply to a request, and finish it with --done", cmd_reply)
    p.add_argument("request")
    p.add_argument("-m", "--message", required=True)
    p.add_argument("--done", action="store_true", help="mark the request done")
    p.add_argument("--version", type=int, help="the version you published (with --done)")
    p = add("watch", "print live events, one line each", cmd_watch)
    p.add_argument("--page", help="only this page")
    p.add_argument("--count", type=int, help="stop after this many events")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.needs_client:
            base, token = config.credentials(args.url)
            args.handler(args, Client(base, token))
        else:
            args.handler(args)
    except CliError as err:
        print(f"error: {err.message}", file=sys.stderr)
        return err.code
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
