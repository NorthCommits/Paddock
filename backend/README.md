# Paddock backend

The Paddock API. Python 3.12, FastAPI, SQLAlchemy 2 (async) and Neon Postgres.

Design documents are in [`docs/`](docs): [PRD](docs/PRD.md), [Architecture](docs/ARCHITECTURE.md) and [SDD](docs/SDD.md).

## What works today

| Area | Endpoints |
|---|---|
| Operations | `GET /healthz`, `GET /readyz` |
| Accounts | `POST /v1/auth/signup`, `POST /v1/auth/login`, `POST /v1/auth/logout`, `GET /v1/me` |
| API tokens | `POST /v1/tokens`, `GET /v1/tokens`, `DELETE /v1/tokens/{id}` |
| Pages | `POST /v1/pages`, `GET /v1/pages`, `GET/PATCH/DELETE /v1/pages/{id}` |
| Versions | `POST /v1/pages/{id}/versions`, `GET /v1/pages/{id}/versions`, `GET /v1/pages/{id}/versions/{n}`, `POST /v1/pages/{id}/versions/{n}/rollback` |
| Email | `POST /v1/auth/verify-email`, `POST /v1/auth/forgot-password`, `POST /v1/auth/reset-password`, `POST /v1/me/verification/resend` |
| Profile | `PATCH /v1/me`, `POST /v1/me/password`, `GET /v1/me/sessions`, `DELETE /v1/me/sessions/{id}`, `POST /v1/me/sessions/revoke-others` |
| Sharing | `GET/POST /v1/pages/{id}/invites`, `GET/POST /v1/pages/{id}/links`, `GET /v1/pages/{id}/members`, role changes, removal, `POST /v1/invites/{token}/accept`, `GET /v1/shared/{token}` |
| Viewing | `POST /v1/pages/{id}/view-url`, then open the URL on the content server |
| Comments | `GET/POST /v1/pages/{id}/comments`, `PATCH/DELETE /v1/comments/{id}`, `POST /v1/comments/{id}/resolve` |
| Requests | `GET /v1/requests`, `POST /v1/requests/{id}/claim`, `.../complete`, `.../dismiss` |

| Live events | `GET /v1/events` (all your pages), `GET /v1/pages/{id}/events` (one page). Server-sent events, scope `events:read` |
| Webhooks | `POST/GET /v1/webhooks`, `PATCH/DELETE /v1/webhooks/{id}`, `POST /v1/webhooks/{id}/test`, `GET /v1/webhooks/{id}/deliveries` |

An `@agent` mention by a person opens a revision request. An agent token lists requests, claims one, publishes a version and completes it. An agent can learn about new requests by holding a live stream open or by receiving a webhook, so it does not need to poll.

## Requirements

- [uv](https://docs.astral.sh/uv/) (it installs the right Python for you)
- A Neon project (free plan is enough)

## Setup

```
cd backend
cp .env.example .env      # then fill in the values below
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The web app lives in [`../frontend`](../frontend). Published pages are served by a second, separate server so their scripts never share an origin with the app:

```
uv run uvicorn app.content:app --port 8001
```

Then open:
- http://localhost:8000/docs for the interactive API reference
- http://localhost:8000/readyz, which should show `{"status":"ready"}` when the database is reachable

## Configuration

Settings come from environment variables or `backend/.env`. Never commit `.env`.

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Neon pooled address, used by the app | required |
| `DATABASE_URL_UNPOOLED` | Neon direct address, used by migrations | falls back to `DATABASE_URL` |
| `SECRET_KEY` | Signs CSRF values. Must be set in production | development placeholder |
| `ENVIRONMENT` | `development`, `test` or `production`. Production turns on secure cookies | `development` |
| `APP_ORIGIN` | Address of the frontend, allowed by CORS. The frontend normally reaches the API through its own `/api` proxy | `http://localhost:3000` |
| `CONTENT_ORIGIN` | Address that will serve published pages | `http://localhost:8001` |
| `STORAGE_BACKEND` | Where files are kept. Only `local` for now | `local` |
| `STORAGE_LOCAL_PATH` | Folder for stored files | `storage` |
| `CONTENT_TOKEN_MINUTES` | Lifetime of a view link | `15` |
| `EMAIL_BACKEND` | `console` logs emails (development). `smtp` sends them. Must be `smtp` in production | `console` |
| `EMAIL_FROM` | Sender shown on emails, such as `Paddock <noreply@yourdomain.com>` | `Paddock <noreply@localhost>` |
| `SMTP_HOST`, `SMTP_PORT` | Your mail server | none, `587` |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Mail server login | none |
| `SMTP_SECURITY` | `starttls` (port 587), `ssl` (port 465) or `none` | `starttls` |
| `VERIFY_EMAIL_HOURS` | How long a confirmation link works | `24` |
| `RESET_PASSWORD_MINUTES` | How long a reset link works | `60` |
| `SESSION_DAYS` | Browser login lifetime | `30` |
| `WEBHOOK_WORKER` | Run the webhook sender inside the API process. Turn off only if you run no webhooks | `true` |
| `WEBHOOK_ALLOW_PRIVATE` | Allow webhook addresses on private networks. For testing on your own machine only, never in production | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

Generate a strong secret with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Email: verification and password reset

Paddock sends its own email through any SMTP server. It does not use Neon or any other service for this.

- **Development:** leave `EMAIL_BACKEND=console`. Emails are printed in the backend log, including the link, so you can click it without a mail account.
- **Real sending:** create a sending account with a provider (Resend, Brevo, Zoho Mail, Amazon SES or your own server), verify your domain with them, then set:

  ```
  EMAIL_BACKEND=smtp
  EMAIL_FROM=Paddock <noreply@yourdomain.com>
  SMTP_HOST=smtp.yourprovider.com
  SMTP_PORT=587
  SMTP_USERNAME=...
  SMTP_PASSWORD=...
  ```

  Also add the SPF and DKIM records your provider gives you, or messages will land in spam.
- **Rules:** a new account gets a confirmation email. Until it is confirmed the person can sign in and read, but cannot publish pages or create tokens (`403 email_not_verified`). Links work once, confirmation links last 24 hours and reset links 1 hour. A reset signs the person out everywhere. "Forgot password" answers the same whether or not the email has an account. A person can ask for another email once a minute.

## How agents connect

1. Sign up and log in through the browser (or the API docs page).
2. Create a token with the scopes you want, using `POST /v1/tokens`. The secret starts with `pdk_` and is shown once.
3. The agent sends it on every request:

   ```
   curl -H "Authorization: Bearer pdk_your_token" http://localhost:8000/v1/me
   ```

Scopes: `pages:read`, `pages:write`, `comments:read`, `comments:write`, `requests:act`, `events:read`.

Tokens cannot create or list other tokens. Only a browser session can manage tokens.

## Live events (server-sent events)

Every change writes an event row in the same transaction. After the commit, open streams receive it at once.

```
curl -N -H "Authorization: Bearer pdk_your_token" http://localhost:8000/v1/events
```

- The token needs `events:read`. `/v1/events` covers pages you own and pages shared with you. `/v1/pages/{id}/events` covers one page.
- Each message has `id`, `event` (the type) and `data` (the envelope below). Reconnect with a `Last-Event-ID` header and the server replays what you missed, up to 1000 events. Beyond that it sends `event: resync`, which means refetch the page data.
- A `: ping` line arrives every 20 seconds. Access is checked again for every event, so a removed member stops receiving at once. Who joined or left a page (`member.added`, `member.removed`) goes to the owner only.
- Streams do not hold a database connection while idle.

Envelope: `{"id": 42, "type": "request.created", "page_id": "...", "created_at": "...", "data": {...}}`

| Type | `data` |
|---|---|
| `version.published` | `version`, `message`, `by_agent` |
| `version.rolled_back` | `version`, `restored`, `by_agent` |
| `page.updated` | the fields that changed (`title`, `slug`, `visibility`) |
| `page.deleted` | empty |
| `comment.created` | `comment_id`, `thread_id`, `body`, `by_agent`, `mentions_agent`, `request_id` |
| `comment.updated` | `comment_id`, `body` |
| `comment.deleted` | `comment_id` |
| `comment.resolved` | `comment_id`, `resolved` |
| `request.created` | `request_id`, `comment_id`, `thread_id`, `body`, `base_version` |
| `request.claimed` | `request_id`, `expires_at` |
| `request.reopened` | `request_id` |
| `request.completed` | `request_id`, `result_version` |
| `request.dismissed` | `request_id`, `reason` |
| `member.added`, `member.removed` | `user_id`, `role` or `left` |

## Webhooks

A webhook is an address on your server that Paddock calls for each matching event on pages you own.

1. Register it: `POST /v1/webhooks` with `{"url": "https://example.com/paddock", "event_types": ["request.created"]}`. Leave `event_types` empty for every event. The response includes a `secret` (starts with `whsec_`). It is shown once, so save it.
2. Try it: `POST /v1/webhooks/{id}/test` sends a `webhook.test` event once and reports what your server answered.
3. Check your server's answers: `GET /v1/webhooks/{id}/deliveries`.

Each call is a `POST` with a JSON body (the envelope above) and these headers:

| Header | Meaning |
|---|---|
| `X-Paddock-Event` | The event type |
| `X-Paddock-Delivery` | A unique id for this delivery |
| `X-Paddock-Timestamp` | Unix time in seconds when the call was signed |
| `X-Paddock-Signature` | `v1=` followed by the hex HMAC-SHA256 of `timestamp + "." + raw body`, keyed with your secret |

Verify it before you trust it, and reject old timestamps (for example older than 5 minutes):

```python
import hashlib, hmac

def valid(secret: str, timestamp: str, body: bytes, header: str) -> bool:
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("v1=" + mac, header)
```

- Any `2xx` answer counts as delivered. Anything else, a timeout (10 seconds) or a connection error is retried after 1 minute, 5 minutes, 30 minutes, 2 hours and 6 hours, then marked `failed`. Redirects are not followed.
- Paddock refuses addresses that point to private or internal networks (loopback, `10.x`, `192.168.x`, link-local and cloud metadata addresses). The check runs when you register and again before every delivery. In production the address must use `https`.
- You can have up to 10 webhooks. Tokens need `events:read` to manage them.
- A background worker sends deliveries. It sleeps until a delivery is due, so an idle service does not keep the database awake. If the host stops the service (a free plan that sleeps), pending deliveries are sent when it wakes.

## Tests and code quality

```
uv run pytest            # all tests
uv run ruff check .      # lint
uv run ruff format .     # format
```

Tests start a throwaway local Postgres through the `pixeltable-pgserver` package and never touch your Neon database. To use a different test database, set `TEST_DATABASE_URL`.

## Database migrations

```
uv run alembic revision --autogenerate -m "describe the change"   # create a migration
uv run alembic upgrade head                                       # apply
uv run alembic downgrade -1                                       # undo the last one
```

Migrations use `DATABASE_URL_UNPOOLED`. Always read a generated migration before applying it.

## Project structure

```
app/
  api/        routes and shared dependencies (who is calling, which scope is needed)
  core/       settings, errors, security helpers, permission rules
  db/         tables, database session, address handling
  schemas/    request and response shapes
  services/   business logic, called by the routes
  main.py     application setup
migrations/   Alembic migrations
tests/        automated tests
docs/         PRD, architecture and design documents
```

## Notes for Neon

- The free plan pauses compute after 5 minutes of inactivity. The first request after a pause can take a few seconds.
- The app uses the pooled address. The code turns off the driver's statement caches for it, because the pooler needs that.
- Migrations and database tools such as DBeaver should use the direct address (the host without `-pooler`).

## Troubleshooting

| Symptom | What to check |
|---|---|
| `/readyz` returns `database_unavailable` | Is `DATABASE_URL` correct? Wait a few seconds if Neon was asleep, then retry. |
| `SECRET_KEY must be set in production` | Set `SECRET_KEY` when `ENVIRONMENT=production`. |
| Login works but the next request says sign in required | In production, cookies are secure and need HTTPS. Use `ENVIRONMENT=development` locally. |
| 403 "Missing or invalid CSRF token" | Send the `csrf_token` from login or `/v1/me` in an `X-CSRF-Token` header on every browser request that changes data. |
