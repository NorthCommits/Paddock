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

Comments, requests and real-time streams are planned in later milestones (see SDD section 13).

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
