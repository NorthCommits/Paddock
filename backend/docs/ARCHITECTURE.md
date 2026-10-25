# Paddock: Architecture (v1 backend)

Status: Draft for review
Related: PRD.md, SDD.md

## 1. Overview

Paddock is a single Python service backed by Postgres and object storage. Agents and the Next.js frontend talk to it over HTTPS. Real-time updates flow to clients over server-sent events (SSE) and optionally to servers over signed webhooks.

```
                   +--------------------+
  Agent CLI / API  |                    |   SQL     +----------------+
  (token auth) --->|                    |---------->| Neon Postgres  |
                   |   Paddock API      |           +----------------+
  Next.js app  --->|   (FastAPI)        |  objects  +----------------+
  (cookie auth)    |                    |---------->| Object storage |
                   |   Event hub (SSE)  |           +----------------+
                   |   Webhook worker   |
                   +---------+----------+
                             |
        pages served from a separate content origin
                             v
                   +--------------------+
  Browser iframe ->|  Content gateway   |--> reads files from object storage
                   +--------------------+
```

## 2. Technology choices

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 or newer | Chosen by the owner. |
| Web framework | FastAPI with Uvicorn | Async, typed, automatic OpenAPI schema, native SSE support. |
| Database | Neon Postgres (free plan) | Free, standard Postgres, branching for safe testing. |
| DB access | SQLAlchemy 2 (async) with asyncpg | Mature and typed. |
| Migrations | Alembic | Versioned schema changes. |
| Validation | Pydantic v2 | Shared with FastAPI. |
| Passwords | Argon2id | Current best practice. |
| Object storage | S3-compatible client (boto3 or aioboto3) behind an interface | Works with Neon object storage and Cloudflare R2 and local disk for development. |
| Tests | pytest, httpx, a Neon branch or local Postgres for integration tests | Fast feedback. |
| CLI | Python (Typer), published as a package | Same language as the backend, easy for agents to run. |
| Packaging | uv for dependencies, Docker for deployment | Reproducible builds. |

## 3. Components

1. **API service.** All REST endpoints, authentication, authorisation, validation and business rules.
2. **Event hub.** Receives domain events after a database commit and pushes them to connected SSE clients. Also writes each event to the durable events table, which is the source of truth for replay.
3. **Webhook worker.** Reads pending deliveries from an outbox table, signs and sends them, and retries with backoff. Runs as a background task in the same process in v1.
4. **Content gateway.** Serves published files from the separate content origin, applying a strict security policy. Implemented as a separate FastAPI app (or a route group mounted on a different host) so it can be deployed and scaled independently.
5. **CLI.** A thin client over the public API. It adds no logic that the API lacks.

## 4. Real-time design (no polling)

### 4.1 Delivery paths

| Audience | Mechanism | Notes |
|---|---|---|
| Browser viewers | SSE stream `GET /v1/pages/{id}/events` | One-way push, auto-reconnect built into browsers. |
| Agent on a laptop | SSE stream `GET /v1/events` through `paddock watch` | An agent on a laptop cannot receive inbound calls, so it holds an outbound stream open. |
| Public servers | Signed webhooks | Optional. For agents that run on a reachable address. |

### 4.2 Durable events with replay

Every domain event (comment created, version published, request claimed, and so on) is written to an append-only `events` table inside the same transaction as the change that caused it. The row has an increasing numeric id. After the transaction commits, the event is handed to the in-process hub, which pushes it to subscribers.

When a client connects with a `Last-Event-ID` header, the server first replays events newer than that id from the table, then switches to live push. This guarantees no lost events across disconnects, restarts and deploys.

### 4.3 Why not Postgres LISTEN/NOTIFY in v1

An earlier idea was to fan events out with LISTEN/NOTIFY. On the Neon free plan, a permanent listening connection keeps the compute awake around the clock and would use the monthly compute allowance (100 compute-hours) in under a month. Neon also suspends compute after 5 minutes of inactivity, which is acceptable for the database but not for a permanent listener.

Decision for v1: run a single API instance with an in-process hub plus the durable events table for replay. The hub is an interface, so a LISTEN/NOTIFY or Redis implementation can be added when Paddock moves to multiple instances or a paid plan.

### 4.4 Cold starts

With scale-to-zero, the first query after idle time is slower. Open SSE connections do not hold a database connection, so idle streams do not keep Neon awake. Only real activity does.

## 5. Data and storage

- **Postgres** stores accounts, tokens, pages, versions, file manifests, memberships, share links, comments, requests, events, webhooks and audit records.
- **Object storage** stores file contents, addressed by SHA-256 hash. Identical files across versions are stored once, which keeps storage small and makes rollback free.
- The free database is limited to 1 GB per project, so file contents never go in Postgres.

Region note: the Neon project lives in AWS US East 2 (Ohio). The backend should be hosted in or near that region to avoid cross-ocean latency on every query.

## 6. Security architecture

Pages contain scripts supplied by agents, so they must be treated as untrusted code.

1. **Separate content origin.** The dashboard and API live on one registrable domain. Pages are served only from a different registrable domain (not a subdomain). Browsers then isolate cookies and storage between them.
2. **Sandboxed frames.** The frontend embeds pages in an iframe with the `sandbox` attribute (scripts allowed, same-origin not granted for the dashboard).
3. **Content security policy** on every content response: restrict network access from page scripts by default, block framing by other sites, and disallow plugins. The owner may later opt in to specific external hosts.
4. **No credentials on the content origin.** Pages are fetched with a short-lived signed URL or view token, never with the dashboard session cookie.
5. **Token hygiene.** API tokens are random, stored only as hashes, shown once, scoped and revocable. Passwords use Argon2id.
6. **Upload validation.** Limits on bundle size, file count and path format, plus content-type allow-listing and path traversal protection.
7. **Authorisation on every query.** Access is checked in a single policy module, not scattered across handlers.
8. **Abuse controls.** Rate limits per token and per IP on publish, comment and login endpoints. Public link pages carry a no-index header by default.
9. **Webhook safety.** Signatures (HMAC) on every delivery, and blocking of private network addresses to prevent server-side request forgery.

## 7. Request flows

### 7.1 Publish

1. Agent calls `POST /v1/pages` or `POST /v1/pages/{id}/versions` with a bundle.
2. API authenticates the token, checks scope and role, validates the bundle.
3. Files are hashed. Missing blobs are written to object storage.
4. In one transaction: create the version, write the file manifest, update the page's current version, write the `version.published` event and audit record.
5. After commit, the hub pushes the event to watchers.

### 7.2 Comment with @agent

1. A collaborator posts a comment.
2. API stores it. If it contains the @agent mention, it also creates a revision request in state `open`, linked to the current version.
3. Events `comment.created` and `request.created` are written and pushed.
4. A watching agent receives `request.created`, claims it, reads the page and thread, publishes a new version, replies, and marks the request done.

### 7.3 Viewing a page

1. The frontend asks the API for a short-lived view URL for the page version.
2. The browser loads that URL on the content origin inside a sandboxed iframe.
3. The content gateway verifies the signed URL, then streams the file from object storage with security headers.

## 8. Repository layout (target)

```
Paddock/
  backend/
    docs/            PRD.md, ARCHITECTURE.md, SDD.md
    app/
      api/           routers and dependencies
      core/          config, security, errors, logging
      db/            models, session, migrations
      services/      business logic (pages, versions, comments, requests, sharing)
      events/        hub, outbox, webhook worker
      storage/       storage interface and implementations
      content/       content gateway app
    cli/             paddock command line tool
    tests/
    pyproject.toml
    Dockerfile
  frontend/          Next.js app (first release built: landing, auth, tokens; see frontend/docs/DESIGN.md)
  neon.ts            Neon project configuration
```

## 8.1 Frontend integration

The Next.js app (`frontend/`) calls the API through a same-origin proxy: Next rewrites `/api/:path*` to the backend (`BACKEND_URL`, default `http://localhost:8000`). The browser therefore sends the `paddock_session` cookie to its own origin, and the frontend reads the CSRF value from sign up, log in or `GET /v1/me` and sends it as `X-CSRF-Token` on every state-changing request. Agents use bearer tokens and never touch the proxy.

## 9. Deployment

- One container image for the API and content gateway (two entry points).
- Configuration through environment variables only. Secrets are kept in `.env` locally and in the host's secret store in production, never committed.
- Database migrations run as a release step.
- Health endpoint at `/healthz` and readiness at `/readyz` (checks the database).
- Hosting provider is not yet chosen. Candidates: a small VM or container platform in or near US East.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Untrusted scripts attack other users | Separate content domain, sandboxed iframe, strict CSP, no credentials on content origin. |
| Neon free plan limits (1 GB storage, 100 compute-hours, cold starts) | Files outside Postgres, no permanent DB connections, small events table with retention policy. |
| Single instance cannot scale out | Hub is an interface, with durable replay so a second implementation is straightforward. |
| Object storage provider immaturity or limits | Storage interface and content hashing allow a move without changing the API. |
| Abuse of free hosting | Rate limits, size limits, abuse report endpoint, no-index headers. |
