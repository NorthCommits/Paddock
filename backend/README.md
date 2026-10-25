# Paddock backend

The Paddock API. Python 3.12, FastAPI, SQLAlchemy 2 (async) and Neon Postgres.

Design documents are in [`docs/`](docs): [PRD](docs/PRD.md), [Architecture](docs/ARCHITECTURE.md) and [SDD](docs/SDD.md).

## What works today

| Area | Endpoints |
|---|---|
| Operations | `GET /healthz`, `GET /readyz` |
| Accounts | `POST /v1/auth/signup`, `POST /v1/auth/login`, `POST /v1/auth/logout`, `GET /v1/me` |
| API tokens | `POST /v1/tokens`, `GET /v1/tokens`, `DELETE /v1/tokens/{id}` |

Pages, versions, sharing, comments, requests and real-time streams are planned in later milestones (see SDD section 13).

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

The web app lives in [`../frontend`](../frontend). Then open:
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
| `SESSION_DAYS` | Browser login lifetime | `30` |
| `LOG_LEVEL` | Logging level | `INFO` |

Generate a strong secret with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

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
