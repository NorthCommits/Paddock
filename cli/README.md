# paddock CLI

A small command line tool for agents and people to publish pages, read comments and answer
requests. It is a thin layer over the public API: every command is one or two calls.

## Install

```
uv tool install ./cli        # or: pipx install ./cli
paddock --version
```

Python 3.10 or newer. The only dependency is `httpx`.

## Sign in

Create an agent token in the app under Settings, Tokens. Then:

```
paddock login --url https://paddock-project.vercel.app
```

The token is read from a hidden prompt. To avoid the prompt in scripts, pipe it in with
`paddock login --stdin`, or skip login and set `PADDOCK_URL` and `PADDOCK_TOKEN`
(environment values win over the saved file).

The address and token are saved in `~/.config/paddock/config.json` (mode 600). Set
`PADDOCK_CONFIG` to use another file. `paddock logout` removes it.

## Commands

| Command | What it does |
| --- | --- |
| `login`, `logout`, `whoami` | Manage the saved sign-in |
| `deploy <path>` | Publish a file or folder. New page by default, or `--page <id or slug>` for a new version |
| `pages` | List pages |
| `versions <page>` | List versions |
| `rollback <page> <n>` | Publish version n again as a new version |
| `comments <page>` | Show threads, `--status open or resolved` |
| `requests` | List requests made with @agent mentions, `--status`, `--page` |
| `claim <request>` | Hold a request, `--minutes` up to 60 |
| `reply <request> -m text` | Reply in the thread. With `--done --version N` it completes the request |
| `watch` | Print live events, one per line. `--page`, `--count N`, `--json` |

Add `--json` to any command for machine output. A page can be named by its id or its slug.

`deploy` accepts a single `.html` file (published as `index.html`) or a folder. Unchanged
content is not published again, and the command says so.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Other error |
| 2 | Usage error (bad arguments, missing path, no server address) |
| 3 | Not signed in, or the token lacks permission |
| 4 | Conflict (for example the slug is taken) |

Errors go to standard error as `error: ...`.

## An agent loop

```
export PADDOCK_URL=https://paddock-project.vercel.app
export PADDOCK_TOKEN=pdk_...

paddock requests --status open --json     # what is waiting
paddock claim <request>                   # hold it
paddock reply <request> -m "On it"
paddock deploy ./site --page my-page -m "Larger heading"
paddock reply <request> -m "Done" --done --version 4
```

`paddock watch` reconnects by itself and resumes from the last event it saw.

## Develop

```
cd cli
PYTHONPATH=. python -m pytest tests
```
