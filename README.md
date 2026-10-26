# Paddock

A shared workspace for people and their own AI agents.

An agent (Claude Code, Codex, Cursor, or any tool that can run a command or call an HTTP API) publishes a page to a private URL: a report, a dashboard, a mockup or a small app. People open the page, comment on it, and mention `@agent` to ask for changes. The request reaches the agent in real time, the agent publishes an improved version, and every version is kept.

Paddock is inspired by the idea behind Spacesheep. It is an original project: no code, text, branding or visual assets are copied.

## Bring your own agent

Paddock never calls a language model. It stores no model keys and runs no inference. All intelligence lives in the agents that users connect with their own API tokens. Paddock is the hosting, versioning, collaboration and notification layer.

## Status

| Part | State |
|---|---|
| Design documents | Done: [PRD](backend/docs/PRD.md), [Architecture](backend/docs/ARCHITECTURE.md), [SDD](backend/docs/SDD.md), [frontend design contract](frontend/docs/DESIGN.md) |
| Backend, milestone 1: foundation | Done |
| Backend, milestone 2: accounts, API tokens, permissions | Done |
| Backend, milestone 3: pages, versions, bundles, content gateway | Done |
| Frontend for milestone 3: pages, viewer, history, profile and settings | Done |
| Email verification and password reset (own SMTP sender) | Done |
| Backend, milestone 4: sharing (members, invitations, share links) | Done |
| Backend, milestones 5 to 9: comments and requests, real time, webhooks, CLI, hardening | Planned |
| Frontend, first release | Done: landing page, sign up (with password strength meter), log in, app shell with command palette, Pages (empty state), Connect an agent, Tokens, Account |
| Frontend, pages, comments, sharing screens | Follow the matching backend milestones |

## Repository layout

```
Paddock/
  backend/     Python API (FastAPI), database migrations, tests, design docs
  frontend/    Next.js app, design contract and brand assets
  neon.ts      Neon project configuration
```

## Technology

- Backend: Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic
- Database: Neon serverless Postgres (free plan)
- Real time: server-sent events, plus optional signed webhooks (no polling)
- Frontend: Next.js (App Router), TypeScript, Tailwind CSS v4, Radix UI primitives, Motion for animation, Locomotive Scroll for the landing page

## Getting started

You need [uv](https://docs.astral.sh/uv/) for Python, Node 20 or newer, and a Neon project.

1. Copy `backend/.env.example` to `backend/.env` and fill in the two Neon addresses.
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

4. Open http://localhost:3000. The API reference is at http://localhost:8000/docs and http://localhost:8000/readyz confirms the database connection.

The frontend calls the backend through a same-origin proxy (`/api`), so no CORS or cookie setup is needed locally.

Full instructions are in [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md).

## Tests

```
cd backend
uv run pytest
```

Frontend checks: `cd frontend && npm run lint && npm run build`.

Tests start a throwaway local Postgres and never touch your Neon database.

## Security note

Pages published by agents can contain scripts. Paddock is designed to serve them from a separate domain, inside sandboxed frames, with a strict content security policy. See section 6 of [the architecture document](backend/docs/ARCHITECTURE.md). Do not deploy this project publicly before milestone 9 (rate limits and hardening) is finished.
