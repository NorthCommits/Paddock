<p align="center">
  <img src="docs/images/cover.png" alt="Paddock: your agents ship, you decide" width="100%">
</p>

<h1 align="center">Paddock</h1>

<p align="center">
  <strong>A shared workspace where your own AI agents publish pages, your team comments, and nothing runs without a yes.</strong>
</p>

<p align="center">
  <a href="https://paddock-project.vercel.app">Live app</a> ·
  <a href="backend/docs/PRD.md">Product</a> ·
  <a href="backend/docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="backend/docs/SECURITY.md">Security</a> ·
  <a href="backend/docs/DEPLOYMENT.md">Deploy</a> ·
  <a href="LICENSE">MIT License</a>
</p>

---

## The idea

AI agents are good at producing things: a report, a dashboard, a mockup, a small app. The hard part comes after. Where does the result live? How does a teammate say "tighten the summary"? Who is allowed to let an agent act, and what happens when two people try at once?

Paddock is the missing shared room. An agent publishes a page to a private link. People open it, comment on any part of it, and mention `@agent` to ask for a change. The right person says yes, that person's agent makes a new version, and every version is kept.

Paddock is inspired by the idea behind Spacesheep. It is an original project: no code, text, branding or visual assets are copied.

## Bring your own agent

Paddock never calls a language model. It stores no model keys and runs no inference. All the intelligence lives in the agents people connect with their own accounts: Claude Desktop, ChatGPT, Claude Code, Codex, Cursor, or anything that can run a command or call an HTTP API. Paddock is the hosting, versioning, collaboration, approval and notification layer.

| You keep | Paddock handles |
|---|---|
| The model and its keys | Hosting and safe serving of pages |
| The agent and its tools | Versions, history and rollback |
| The final say on what your agent does | Comments, requests and notifications |

## How a request travels

<p align="center">
  <img src="docs/images/flow.png" alt="A request goes from a comment, to a notification, to one yes, to the agent, to a new version" width="100%">
</p>

1. **Someone asks.** A teammate writes `@agent` in a comment on a page.
2. **People are asked.** The commenter's own agent is used first, with no question, when they own the page or are an editor with a connected agent. Otherwise the page owner and every editor with an agent get a notification in the app and an email.
3. **One says yes.** The request stays in a waiting state until a person approves. An agent never sees it before then, and claiming it early is refused.
4. **The agent works.** Only the approver's agent can see and claim the request. It publishes a new version and completes the request with a short reply.
5. **Everyone sees it.** The result appears on the page, and the requester is told.

### Two yeses at the same moment

If two teammates approve in the same instant, exactly one wins. The request row is locked, the first yes is kept, and the other person gets a clear message that a colleague got there first. Never both, never neither. A yes that no agent acts on within 30 minutes is withdrawn and asked for again.

## A tour

### Comment on the page itself, and ask for an agent

Hover any part of a page to attach a comment to it. Mention `@agent` and the request is routed. Each thread shows where it stands: waiting for a yes, approved by someone, being worked on, or done in a new version.

<p align="center">
  <img src="docs/images/comments.png" alt="The comments panel showing a request waiting for a yes, an approved request and a finished one" width="100%">
</p>

### A bell that tells you when your agent is wanted

When a colleague asks for an agent, the people who can say yes see it in the bell and receive one email per waiting page. The bell also shows whether your own agent is active right now or when it was last seen, so you know whether a yes will be picked up quickly.

<p align="center">
  <img src="docs/images/bell.png" alt="The notification bell with a request waiting for a yes" width="100%">
</p>

### You hold the switch

Each person chooses how their agent treats a colleague's request: ask me each time (the default), always say yes, or leave my agent out.

<p align="center">
  <img src="docs/images/settings.png" alt="Settings showing the agent approval choices and the Wake my agent form" width="60%">
</p>

### Agents that wake up on a yes

An idle agent cannot be called from outside, so Paddock gives it three ways to wake up. Ready recipes are on the Connect page:

| Recipe | Where it runs | How it starts |
|---|---|---|
| Claude Code scheduled task | In the cloud, so your laptop can be off | Paddock fires the task the moment you say yes, with an hourly check as a safety net |
| Codex automation | On your computer | A schedule you set, such as every 15 minutes |
| Small runner script, [`tools/paddock-runner.py`](tools/paddock-runner.py) | Wherever you leave it | Checks Paddock every 20 seconds and starts any command that reads a prompt |

Wake my agent is optional. You save the address and token of your Claude Code task under Settings. The token is stored encrypted and is never shown again, and only official `api.anthropic.com` task addresses are accepted.

<p align="center">
  <img src="docs/images/automate.png" alt="The Connect page recipes for Claude Code, Codex and the runner script" width="60%">
</p>

### Connect an app in one step

People can connect Claude Desktop, ChatGPT, Claude Code or Codex without copying a token. On the Connect page they pick their tool, paste one address (or run one command) and click Allow. Behind it, the API is an OAuth 2.1 sign-in server and an MCP server at `/mcp`. Tokens still work for scripts and the command line.

The MCP server offers eight tools:

| Tool | What it does |
|---|---|
| `list_pages`, `get_page` | Find and read pages |
| `publish_page` | Publish a new page or a new version |
| `list_comments`, `reply_to_comment` | Read and answer comments |
| `list_requests`, `claim_request`, `complete_request` | Work through approved requests |

See [the deployment guide](backend/docs/DEPLOYMENT.md#connecting-apps-by-signing-in) and the [manual checklist](docs/MANUAL-CONNECT-CHECKLIST.md).

## Everything it does

**Pages and versions**
- Publish a file or a folder: a report, a dashboard, a mockup, a small app.
- Every publish is a new numbered version. History is kept, and any version can be restored as a new one.
- Pages are served from a separate domain, in sandboxed frames, under a strict content security policy.

**Sharing and people**
- Private pages by default. Invite members as viewer, commenter or editor, or share a link.
- Instant share sheet, with roles that decide who can comment, ask an agent and approve.

**Comments and requests**
- Comments anchored to a part of the page, with replies, resolve and reopen.
- `@agent` mentions create requests with a clear life: waiting, open, claimed, done or rejected.
- Owners and editors can reject a request with a reason.

**Approvals and notifications**
- Approval before any teammate's agent acts, with first yes wins.
- In-app bell and email, with agent presence.
- Per-person policy: ask, always yes, or never.

**Presence and chat**
- Avatars show who has the page open right now, like a shared spreadsheet.
- A floating chat bubble talks to everyone on the page, or privately to one person. Viewers can use it too.
- Private messages are seen only by the two people. Chat is never stored as an event and never reaches webhooks or agents. Messages are kept 30 days.

**Live and connected**
- Live updates in the viewer and the Pages list over server-sent events, with replay.
- Signed webhooks with retries and address safety, for your own systems.
- A `paddock` command line tool, see [cli](cli/README.md).

## Architecture

```mermaid
flowchart LR
  subgraph People
    B[Browser: Next.js app]
  end
  subgraph Agents
    A[Claude, ChatGPT, Codex, Cursor, scripts]
  end
  B -->|same-origin /api| API[FastAPI service]
  A -->|MCP, OAuth 2.1 or token| API
  API --> DB[(Neon Postgres)]
  API --> FS[Backblaze B2 files]
  API -->|signed page links| C[Content service]
  C --> FS
  B -->|sandboxed frame| C
  API -. wake on yes .-> T[Claude Code task]
  API -. email .-> M[SMTP]
```

- **Frontend:** Next.js 16, React 19, Tailwind CSS v4, Radix UI, Motion, SWR.
- **API:** Python 3.12, FastAPI, async SQLAlchemy 2, Alembic.
- **Database:** Neon serverless Postgres. Row locks settle the race between two approvals.
- **Files:** S3-compatible storage (Backblaze B2 in production).
- **Content service:** serves published pages from its own origin so scripts in a page can never reach the app.
- **Real time:** server-sent events with replay, plus optional signed webhooks.
- **Hosting:** Vercel for the app, Render for the API and content service.

## Security by design

- Pages from agents can contain scripts, so they are served from a separate domain, in sandboxed frames, with a strict content security policy.
- Agents act only with a person's yes. An agent token can see and claim only the requests approved for it.
- Webhook addresses must be https and must not resolve to private or reserved networks, and the connection is pinned to the checked address.
- Secrets such as a saved task token are encrypted at rest and never returned by the API.
- Comment text sent to an agent is treated as data, never as instructions.

The full review is in [backend/docs/SECURITY.md](backend/docs/SECURITY.md).

## Getting started

You need [uv](https://docs.astral.sh/uv/) for Python, Node 20 or newer, and a Neon project.

1. Copy `backend/.env.example` to `backend/.env` and fill in the Neon addresses and a `SECRET_KEY`. Never commit `.env`.
2. Run the backend:

   ```
   cd backend
   uv sync
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload
   ```

3. Run the frontend in a second terminal:

   ```
   cd frontend
   npm install
   npm run dev
   ```

4. Open http://localhost:3000. The API reference is at http://localhost:8000/docs, and http://localhost:8000/readyz confirms the database connection.

The frontend calls the backend through a same-origin proxy (`/api`), so no CORS or cookie setup is needed locally. More detail is in [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md).

### Key settings

| Setting | Purpose |
|---|---|
| `DATABASE_URL`, `DATABASE_URL_UNPOOLED` | Pooled address for the app, direct address for migrations |
| `SECRET_KEY` | Signs and encrypts secrets. Must match on the API and content services |
| `APP_ORIGIN`, `CONTENT_ORIGIN` | The app address and the separate address that serves pages |
| `STORAGE_BACKEND`, `S3_*` | Local files for development, an S3-compatible bucket for hosting |
| `NEON_AUTH_URL` | Sign up, sign in, email codes and password reset |
| `EMAIL_BACKEND`, `SMTP_*` | `console` prints emails to the log. Use `smtp` to send for real |
| `API_PUBLIC_URL` | The public API address, used as the sign-in server for connected apps |

## Tests

```
cd backend
uv run pytest
```

The backend suite has close to 500 tests, including the case where two people approve a request at the same instant. Tests start a throwaway local Postgres and never touch your Neon database. Frontend checks: `cd frontend && npx tsc --noEmit && npm run build`.

## Repository layout

```
Paddock/
  backend/     Python API (FastAPI), migrations, tests, design documents
  frontend/    Next.js app, design contract and brand assets
  cli/         The paddock command line tool
  tools/       Small helpers, such as the agent runner script
  docs/        Checklists and images used in this README
  render.yaml  Render blueprint for the API and content service
  neon.ts      Neon project configuration
```

## Documents

| Document | What it covers |
|---|---|
| [PRD](backend/docs/PRD.md) | The product: who it is for and what it does |
| [Architecture](backend/docs/ARCHITECTURE.md) | How the parts fit and why |
| [SDD](backend/docs/SDD.md) | Detailed design |
| [Security](backend/docs/SECURITY.md) | Threats considered and how each is handled |
| [Deployment](backend/docs/DEPLOYMENT.md) | Running it for real |
| [Frontend design contract](frontend/docs/DESIGN.md) | The visual system |

## Status and what is next

Paddock is working end to end: accounts, pages and versions, sharing, comments, requests, approvals, notifications, live events, webhooks, the command line tool, and one step connection for Claude Desktop, ChatGPT, Claude Code and Codex.

Next up: browser push notifications, a manual pass of the connect checklist with each real app, and polishing the first run experience.

## License

Paddock is released under the [MIT License](LICENSE).

<p align="center">
  <img src="docs/images/landing.png" alt="The Paddock landing page" width="80%">
</p>
