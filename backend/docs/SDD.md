# Paddock: Software Design Document (v1 backend)

Status: Draft for review
Related: PRD.md (requirements F-01 to F-18), ARCHITECTURE.md

This document defines the data model, API, rules and test plan for the v1 backend. It contains no implementation code.

## 1. Conventions

- All identifiers are UUIDs (version 4), except `events.id`, which is a 64-bit increasing integer.
- All timestamps are stored in UTC.
- All API paths start with `/v1`. Request and response bodies are JSON unless stated.
- Errors use one shape: `{"error": {"code": "string", "message": "string", "request_id": "string"}}`.
- Pagination uses a cursor: `?limit=` and `?cursor=`, with `next_cursor` in the response.

## 2. Data model

### 2.1 Tables

**users**
id, email (unique, lowercase), password_hash, handle (unique, used in URLs), display_name, created_at, disabled_at

**sessions** (browser login)
id, user_id, token_hash, created_at, expires_at, last_seen_at, user_agent, ip

**api_tokens**
id, user_id, name, prefix (first 8 characters, shown in lists), token_hash, scopes (text array), created_at, last_used_at, expires_at, revoked_at

**pages**
id, owner_id, slug (unique per owner), title, visibility (`private`, `members`, `link`), current_version_id, created_at, updated_at, deleted_at

**page_versions** (immutable)
id, page_id, number (1, 2, 3 ... unique per page), message, author_user_id, author_token_id (nullable), entry_path (for example `index.html`), total_bytes, file_count, rolled_back_from (nullable version id), created_at

**version_files**
version_id, path, sha256, size_bytes, content_type. Primary key: (version_id, path).

**blobs**
sha256 (primary key), size_bytes, storage_key, created_at, ref_count (maintained for cleanup)

**page_members**
page_id, user_id, role (`viewer`, `commenter`, `editor`), invited_by, created_at. Primary key: (page_id, user_id).

**page_invites**
id, page_id, email, role, token_hash, created_at, expires_at, accepted_at

**share_links**
id, page_id, token_hash, role (`viewer` or `commenter`), created_by, created_at, expires_at, revoked_at

**comments**
id, page_id, version_id (version the author was looking at), parent_id (nullable, for replies), author_user_id (nullable), author_token_id (nullable), body, anchor (JSON, nullable), mentions_agent (boolean), created_at, edited_at, deleted_at, resolved_at, resolved_by

**revision_requests**
id, page_id, comment_id (unique), requested_by, base_version_id, status (`open`, `claimed`, `done`, `dismissed`), claimed_by_token_id, claim_expires_at, result_version_id, created_at, updated_at

**events** (append-only)
id (bigserial), page_id (nullable), user_id (the owner whose streams should receive it), type, payload (JSON), created_at

**webhooks**
id, user_id, url, secret (stored encrypted), event_types (text array), active, created_at

**webhook_deliveries**
id, webhook_id, event_id, status (`pending`, `delivered`, `failed`), attempts, next_attempt_at, last_status_code, last_error, created_at

**audit_log**
id, user_id, token_id, action, target_type, target_id, metadata (JSON), ip, created_at

### 2.2 Important indexes

- `pages (owner_id, slug)` unique.
- `page_versions (page_id, number)` unique.
- `comments (page_id, created_at)`.
- `revision_requests (page_id, status)` and `(status, claim_expires_at)`.
- `events (user_id, id)` and `events (page_id, id)` for replay.
- `webhook_deliveries (status, next_attempt_at)`.

### 2.3 Retention

- Events older than 30 days are deleted by a daily job, except those needed by pending webhook deliveries.
- Unreferenced blobs (ref_count zero for more than 7 days) are deleted from storage by a daily job.
- Also removed daily: webhook delivery history over 30 days, ended invitations and share links over 30 days, pages deleted over 30 days ago, audit entries over a year old.
- Implemented in `app/services/retention.py`. It runs inside the API process, or on demand with `python -m app.jobs retention`. Each step is safe to repeat.

## 3. Authentication and authorisation

### 3.1 Credentials

| Client | Credential | Details |
|---|---|---|
| Browser | Session cookie | HttpOnly, Secure, SameSite=Lax. Stored as a hash in `sessions`. State-changing requests must send an `X-CSRF-Token` header. The value is derived from the session (an HMAC of the session id with the secret key), nothing extra is stored, and it is returned by login, sign up and `GET /v1/me` so a frontend on another origin can read it. |
| Agent | API token in `Authorization: Bearer pdk_...` | Format: prefix `pdk_` plus 32 random bytes encoded in URL-safe text. Only a SHA-256 hash is stored. Shown once at creation. |

### 3.2 Token scopes

| Scope | Allows |
|---|---|
| `pages:read` | List and read pages the user can access. |
| `pages:write` | Create pages and publish versions to pages the user can edit. |
| `comments:read` | Read comments and requests. |
| `comments:write` | Post comments and replies. |
| `requests:act` | Claim, complete and dismiss revision requests. |
| `events:read` | Open event streams. |

A token never exceeds the permissions of its user. Effective permission is the intersection of token scope and the user's role on the page.

### 3.3 Roles

| Role | View | Comment | Create request | Publish version | Manage sharing | Delete |
|---|---|---|---|---|---|---|
| viewer | yes | no | no | no | no | no |
| commenter | yes | yes | yes | no | no | no |
| editor | yes | yes | yes | yes | no | no |
| owner | yes | yes | yes | yes | yes | yes |

Link visibility grants the link's role (`viewer` or `commenter`) to anyone holding the link token.

### 3.4 Policy module

A single module answers `can(actor, action, page)`. Every route calls it. Tests cover the full matrix of role, scope and action.

## 4. API design

Only the main contract is listed here. The OpenAPI schema generated from the code is the final reference.

### 4.1 Auth and tokens
| Method and path | Purpose |
|---|---|
| POST /v1/auth/signup | Create an account. |
| POST /v1/auth/login | Start a browser session. |
| POST /v1/auth/logout | End the session. |
| GET /v1/me | Current user. |
| POST /v1/tokens | Create a token (returns the secret once). |
| GET /v1/tokens | List tokens (prefix, scopes, last used). |
| DELETE /v1/tokens/{id} | Revoke a token. |

### 4.2 Pages and versions
| Method and path | Purpose |
|---|---|
| POST /v1/pages | Create a page with its first version from a bundle. |
| GET /v1/pages | List pages the actor can access. |
| GET /v1/pages/{id} | Page details and current version. |
| PATCH /v1/pages/{id} | Change title, slug or visibility. |
| DELETE /v1/pages/{id} | Soft delete. |
| POST /v1/pages/{id}/versions | Publish a new version. |
| GET /v1/pages/{id}/versions | List versions. |
| GET /v1/pages/{id}/versions/{number} | Version details and file manifest. |
| POST /v1/pages/{id}/versions/{number}/rollback | Publish an earlier version as the newest. |
| POST /v1/pages/{id}/view-url | Get a short-lived signed URL for the content origin. |

### 4.3 Sharing
| Method and path | Purpose |
|---|---|
| GET /v1/pages/{id}/members | List members (owner only). |
| PATCH /v1/pages/{id}/members/{user_id} | Change a member's role. |
| DELETE /v1/pages/{id}/members/{user_id} | Remove a member. A member can remove themselves (leave). |
| POST /v1/pages/{id}/invites | Invite by email with a role. Emails the invitation and returns the accept link once. |
| GET /v1/pages/{id}/invites | List pending invitations. |
| DELETE /v1/pages/{id}/invites/{invite_id} | Revoke an invitation. |
| GET /v1/invites/{token} | Preview an invitation (page title, inviter, role). Needs no login. |
| POST /v1/invites/{token}/accept | Accept an invitation. Needs a browser session with a confirmed email that matches the invited address. |
| POST /v1/pages/{id}/links | Create a share link (viewer or commenter, optional expiry). The URL is returned once. |
| GET /v1/pages/{id}/links | List live share links (never the secret). |
| DELETE /v1/pages/{id}/links/{link_id} | Revoke a link. |
| GET /v1/shared/{token} | What a link opens (title, owner, role, version number). Needs no login. |
| POST /v1/shared/{token}/view-url | A signed content URL for the page's current version. Needs no login. |

Visibility is a ceiling: `private` is the owner only (members and links stay stored but are switched off), `members` adds invited members, `link` also lets share links work. Creating an invitation or link widens the page to at least what it needs. Pages shared with you appear in `GET /v1/pages` with your `role`.

### 4.4 Comments and requests
| Method and path | Purpose |
|---|---|
| GET /v1/pages/{id}/comments | List comments with threads. |
| POST /v1/pages/{id}/comments | Create a comment or reply. Detects the @agent mention. |
| PATCH /v1/comments/{id} | Edit own comment. |
| DELETE /v1/comments/{id} | Delete own comment (owner and editors may delete any). |
| POST /v1/comments/{id}/resolve | Resolve or reopen a thread. |
| GET /v1/requests | List requests across the actor's pages (filter by status and page). |
| GET /v1/requests/{id} | Read one request, so an agent can find its page and thread. |
| POST /v1/requests/{id}/claim | Claim a request for a limited time. |
| POST /v1/requests/{id}/complete | Mark done with the resulting version number and a reply. |
| POST /v1/requests/{id}/dismiss | Dismiss with a reason. |

### 4.5 Real time and webhooks
| Method and path | Purpose |
|---|---|
| GET /v1/pages/{id}/events | SSE stream for one page. |
| GET /v1/events | SSE stream for all of the actor's pages (used by `paddock watch`). |
| POST /v1/webhooks | Register a webhook. The signing secret is returned once. |
| GET /v1/webhooks | List webhooks. |
| PATCH /v1/webhooks/{id} | Turn on or off, change the event filter. |
| DELETE /v1/webhooks/{id} | Remove a webhook and its deliveries. |
| POST /v1/webhooks/{id}/test | Send a `webhook.test` event once and report the answer. |
| GET /v1/webhooks/{id}/deliveries | Recent deliveries with status, attempts and errors. |

### 4.6 Operations
| Method and path | Purpose |
|---|---|
| GET /healthz | Process is alive. |
| GET /readyz | Database reachable. |

## 5. Business rules

### 5.1 Bundles and uploads

- A bundle is a multipart upload or a single JSON manifest plus file parts. The manifest lists each file's path, size and SHA-256.
- Paths: relative, lowercase letters, digits, dots, dashes, underscores and slashes only. No `..`, no leading slash, no duplicates after normalisation.
- A bundle must contain an entry file (default `index.html`). A single uploaded HTML file is stored as `index.html`.
- Limits (configurable): 25 MB total, 200 files, 10 MB per file.
- Allowed content types: HTML, CSS, JavaScript, JSON, plain text, SVG, PNG, JPEG, GIF, WebP, AVIF, ICO, WOFF, WOFF2, TTF, OTF, and MP4/WebM video. Type is decided from the file extension and verified from content; mismatches are rejected.
- The server recomputes SHA-256 for every file and rejects a mismatch.
- Optional two-step upload: the client sends the manifest first, the server replies with which hashes it lacks, and the client uploads only those. This makes new versions of large pages cheap.

### 5.2 Versions

- Version numbers increase by one per page and are assigned inside the publishing transaction with a row lock on the page to avoid duplicates.
- A version is never modified. Rollback creates a new version that references the same files and records `rolled_back_from`.
- Publishing the identical file set as the current version returns the current version unchanged (idempotent).
- An optional `base_version` field in the publish request lets agents detect concurrent edits: if it is not the current version, the server returns a conflict error with the current version number.

### 5.3 Comments and the @agent mention

- A mention is detected case-insensitively when the body contains `@agent` as a whole word.
- Creating a comment with a mention creates one revision request, linked to the comment and to the page's current version. Replies containing the mention create a new request as well.
- Anchors are optional JSON, for example `{"selector": "...", "quote": "...", "version": 7}`. The server stores them without interpreting them, and validates size only.
- Editing a comment to add the mention creates a request. Removing the mention while the request is still open dismisses it.

Decisions made in milestone 5:

- Only comments written by a person create requests. A comment written by an agent token never does, which prevents loops.
- Replies to a reply attach to the thread root, so threads are one level deep.
- Anchors are kept on the first comment of a thread only and limited to 4096 bytes.
- Only the author can edit. Adding a mention on edit creates or reopens the request. Removing it dismisses an open request with the reason "The mention was removed".
- Deleting is soft. Owners and editors can delete any comment. Deleting dismisses an open or claimed request ("The comment was deleted"). A deleted first comment stays as a placeholder while it has replies.
- Resolve and reopen apply to the first comment of a thread.
- `GET /v1/requests` needs `comments:read` or `requests:act` and lists requests on pages the actor owns or is a member of (not private pages of others), oldest first.

### 5.4 Request state machine

```
open --claim--> claimed --complete--> done
 ^                 |
 |                 +--dismiss------> dismissed
 +--claim expires--+
open --dismiss--> dismissed
```

- A claim lasts 10 minutes by default and can be extended by the same token with another claim call.
- Expired claims return to `open` when requests are listed or claimed, so no background job is needed (milestone 6 emits `request.reopened` when it adds events).
- Only a token with `requests:act` and editor rights on the page can claim or complete. Browser logins cannot (403). Editors, as people or tokens, can dismiss.
- `complete` requires a `result_version` that belongs to the same page and was published after the request was created. It also posts an agent reply into the thread.
- A done or dismissed request cannot change state again.

### 5.5 Sharing

- Invites by email: creating an invite stores a hashed token, emails the invitation through the mailer and returns the accept link once, so the owner can also send it another way. Invitations last 7 days and work once. Accepting needs an account whose confirmed email is the invited address, so a forwarded link is useless to anyone else. A new invitation to the same address replaces the old one.
- Share links can be revoked and can expire. A link never grants editing rights. A link stops working when the page is not set to `link`, is deleted, or the link is revoked or expired; all of these give the same 404. Limits per page: 50 members, 50 pending invitations, 20 live links.
- Link pages are served with `X-Robots-Tag: noindex`.

## 6. Event system

### 6.1 Event types

`version.published`, `version.rolled_back`, `page.updated`, `page.deleted`, `comment.created`, `comment.updated`, `comment.deleted`, `comment.resolved`, `request.created`, `request.claimed`, `request.reopened`, `request.completed`, `request.dismissed`, `member.added`, `member.removed`.

### 6.2 Event envelope

```
{ "id": 1234, "type": "request.created", "page_id": "...", "created_at": "...", "data": { ... } }
```

The `data` object holds enough to act without another call (for example the comment text, the request id and the base version).

### 6.3 Write path

1. The service performs its change and inserts the event in the same transaction.
2. After commit, the service publishes the event to the in-process hub.
3. The hub pushes to subscribers whose permissions allow them to see the event.
4. For each active webhook that matches, the service inserts a pending delivery in the same transaction.

### 6.4 SSE behaviour

- Each message sets `id` to the event id, so browsers send `Last-Event-ID` on reconnect.
- On connect: authenticate, read `Last-Event-ID`, replay missed events (up to 1000, otherwise send a `resync` event telling the client to refetch), then stream live.
- A comment line `: ping` is sent every 20 seconds to keep proxies from closing the connection.
- Permissions are checked at connect time and re-checked on each event, so removed members stop receiving events.

Decisions made in milestone 6:

- `GET /v1/events` covers pages the person owns and pages shared with them (not private ones). `GET /v1/pages/{id}/events` needs read access to that page. Both need the `events:read` scope.
- The owner alone receives `member.added` and `member.removed`. The owner still receives `page.deleted` for a deleted page; other people do not.
- The stream is started without holding a database connection. Each event is checked with a short query, so an idle stream does not use the database.
- The event row is written with `emit()` in the same transaction as the change. A SQLAlchemy `after_commit` hook hands the row to the hub, and `after_rollback` drops it, so a failed change never reaches a stream.
- Each stream has a queue of 500 events. A client that falls further behind is sent `resync` and disconnected, then reconnects and replays.
- Event ids are assigned when the row is written. Two transactions that overlap can commit out of order, so on a reconnect an event could in rare cases be missed. A client that needs certainty should refetch after a `resync` or a long disconnect.
- Event retention (30 days) is a daily job that belongs to milestone 9.
- Per-user limit on concurrent streams (default 10).

### 6.5 Webhooks

- Headers: `X-Paddock-Event`, `X-Paddock-Delivery`, `X-Paddock-Timestamp`, `X-Paddock-Signature` (`v1=` plus the hex HMAC-SHA256 of `timestamp.body` with the webhook secret).
- Success is any 2xx within 10 seconds. Failures retry after 1 minute, 5 minutes, 30 minutes, 2 hours and 6 hours (six attempts in all), then are marked failed.
- Target URLs must be HTTPS in production and must resolve only to public addresses. The check runs at registration and again before every attempt. Redirects are not followed.

Decisions made in milestone 7:

- Only the owner of a page receives webhook deliveries for it, matching the event's `user_id`. An empty `event_types` list means every event. `webhook.test` is sent regardless of the filter.
- The signing secret is generated by Paddock (`whsec_...`), shown once, and stored encrypted with a key derived from `SECRET_KEY` (Fernet). Changing `SECRET_KEY` makes existing secrets unreadable, so webhooks must be recreated.
- Deliveries are inserted in the same transaction as the event. The worker runs inside the API process, takes due rows with `FOR UPDATE SKIP LOCKED`, and sleeps until the next due time or until a commit wakes it. It never polls on a timer, so it does not keep the database awake. On start it sends anything left pending.
- A test call is attempted once and never retried.
- A turned-off or deleted webhook stops its pending deliveries (they are marked failed, or removed with the webhook).
- Limits: 10 webhooks per person. Managing webhooks needs a signed-in person or a token with `events:read`.
- Known limit: the address check and the send use separate name lookups, so a hostile DNS server could in theory switch answers between them. Pinning the connection to the checked address is a hardening task for milestone 9.

## 7. Content gateway

- Route: `GET /c/{token}/{path}` on the content origin. The signed token (page id, version, expiry, 15 minutes by default) sits in the URL path, not in `?t=` or a cookie, so relative asset links work and it also works inside cross-site iframes. Built in milestone 3 as a separate ASGI app: `uvicorn app.content:app --port 8001`.
- Uploads: multipart (`files` parts, optional `manifest` of path and sha256) or JSON (`{"files":[{"path","content","encoding"}]}`), both checked by the same bundle rules. Storage is local disk behind an interface; S3 and two-step upload come later.
- The token binds page, version, expiry and audience. Default lifetime: 15 minutes.
- Files stream from object storage using the stored content type.
- Headers on every response: `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-site`, and a cache policy of `private, max-age=300` for versioned URLs.
- Default CSP: `default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self'; frame-ancestors <dashboard origin>; form-action 'none'; base-uri 'none'`. Page scripts therefore cannot send data to arbitrary hosts.
- Directory requests resolve to the entry file. Unknown paths return 404.

## 8. Storage interface

Operations: `put(sha256, bytes or stream)`, `exists(sha256)`, `open(sha256)`, `delete(sha256)`, and `presign_get(sha256)` where supported.
Implementations: local disk (development and tests), S3-compatible (Neon object storage or Cloudflare R2). Keys are `blobs/<first two hex chars>/<sha256>`.

## 9. CLI design

Command name: `paddock`. Configuration is stored in the user's config directory. The token can also come from `PADDOCK_TOKEN`.

| Command | Purpose |
|---|---|
| `paddock login` | Store a token (created in the dashboard) and server URL. |
| `paddock deploy <file or folder> [--page <id or slug>] [-m "message"]` | Create a page or publish a new version. Prints the URL and version. |
| `paddock pages` | List pages. |
| `paddock versions <page>` | List versions. |
| `paddock rollback <page> <version>` | Roll back. |
| `paddock comments <page>` | Show threads. |
| `paddock requests [--status open]` | List requests. |
| `paddock watch [--page <id>] [--json]` | Keep a stream open and print each event as one line (plain or JSON), so an agent can react immediately. |
| `paddock claim <request>` | Claim a request. |
| `paddock reply <request> -m "text" [--done --version N]` | Reply and optionally complete. |

Exit codes: 0 success, 1 general error, 2 usage error, 3 authentication error, 4 conflict.

Implementation notes: the CLI is the `cli` package (Python, `httpx` only). `paddock login` tries the given address and then the address plus `/api`, because the frontend forwards the API under `/api`. Every command accepts `--json`. A page can be named by id or slug. Requests that get `429` are retried twice after the `Retry-After` wait. `watch` reconnects on its own and resumes from the last event id.

## 10. Configuration

Environment variables (names only; values are never committed):

`DATABASE_URL` (pooled Neon connection), `DATABASE_URL_UNPOOLED` (direct connection, for migrations), `SECRET_KEY`, `APP_ORIGIN`, `CONTENT_ORIGIN`, `STORAGE_BACKEND` (`local` or `s3`), `STORAGE_LOCAL_PATH`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`, `MAX_BUNDLE_BYTES`, `MAX_FILES`, `WEBHOOK_WORKER`, `WEBHOOK_ALLOW_PRIVATE`, `RATE_LIMIT_ENABLED`, `PROXY_HOPS`, `RETENTION_ENABLED`, `LOG_LEVEL`.

Neon note: use the pooled connection for the app and the direct connection for migrations. Connection pool size is kept small to respect free plan limits.

## 11. Error codes

`unauthenticated`, `forbidden`, `not_found`, `validation_failed`, `conflict`, `rate_limited`, `payload_too_large`, `unsupported_media`, `claim_expired`, `invalid_state`, `internal`.

## 12. Test plan

| Area | What is tested |
|---|---|
| Auth | Signup, login, logout, password hashing, session expiry, CSRF. |
| Tokens | Creation, one-time display, hashing, scope enforcement, revocation, expiry. |
| Policy | Full matrix of role, token scope and action. |
| Bundles | Path rules, limits, content-type checks, hash mismatch, traversal attempts. |
| Versions | Numbering under concurrent publishes, idempotent publish, rollback, conflict on stale `base_version`. |
| Sharing | Invites, acceptance, link creation, revocation, expiry, no-index header. |
| Comments | Threads, edits, deletes, resolve, anchor size limit, mention detection. |
| Requests | Every state transition, claim expiry and reopen, invalid transitions, result version checks. |
| Events | Written in the same transaction, replay after reconnect, resync on large gaps, permission filtering. |
| Webhooks | Signature, retries and backoff, private-address blocking. |
| Content gateway | Signed token checks, headers, 404 handling, CSP present on every response. |
| CLI | Each command against a test server, exit codes, `watch` output format. |
| Non-functional | Basic load test of the SSE hub, migration up and down, health endpoints. |

Integration tests run against a temporary Neon branch or a local Postgres, with local disk storage.

## 13. Delivery milestones

1. **Foundation:** project layout, configuration, database connection, migrations, health endpoints, CI.
2. **Accounts:** users, sessions, API tokens, policy module.
3. **Pages and versions:** bundles, storage interface, versions, rollback, content gateway.
4. **Sharing:** members, invites, share links.
5. **Collaboration (done):** comments, mention detection, revision requests and state machine.
6. **Real time (done):** events table, hub, SSE streams, replay.
7. **Webhooks (done):** outbox, worker, signing, retries.
8. **CLI (done):** all commands, packaging, setup guide. See `cli/README.md`.
9. **Hardening (done):** rate limits, retention jobs, load test, security review, Docker image, deployment guide. See `docs/SECURITY.md` and `docs/DEPLOYMENT.md`.

Each milestone ends with passing tests and a short demo before the next begins.
