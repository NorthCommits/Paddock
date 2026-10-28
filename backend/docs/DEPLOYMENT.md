# Paddock: deployment guide

Paddock has three parts: the frontend (Next.js), the API and the content service (both Python,
same code), plus a Postgres database, file storage and Neon Auth.

The live setup uses:

| Part | Where |
| --- | --- |
| Frontend | Vercel |
| API and content service | Render (two web services from `render.yaml`) |
| Database and sign in | Neon |
| Files | Backblaze B2 (any S3 compatible bucket works) |

## 1. Neon

1. Create a project. Enable Neon Auth and note its address, which looks like
   `https://ep-xxx.neonauth.<region>.aws.neon.tech/<database>/auth`. This is `NEON_AUTH_URL`.
2. Copy two connection strings: the pooled one (`DATABASE_URL`) and the direct one
   (`DATABASE_URL_UNPOOLED`, used for migrations).
3. If Neon is set to require a verified email before sign in, set `NEON_AUTH_EMAIL_VERIFIED=true`.

## 2. File storage

Create a private bucket and a key limited to it. You need the bucket name, endpoint, region and
the key pair. Do not make the bucket public: files are only served through the content service.

## 3. API and content service on Render

The Blueprint `render.yaml` defines both services in Ohio, next to Neon. In Render choose
New, Blueprint, pick the repository, and fill in the values it asks for.

Set the same `SECRET_KEY` on both services (at least 48 random characters):

```
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

| Variable | Both services | Notes |
| --- | --- | --- |
| `DATABASE_URL`, `DATABASE_URL_UNPOOLED` | yes | From Neon |
| `NEON_AUTH_URL` | yes | From Neon |
| `SECRET_KEY` | yes | Must match |
| `APP_ORIGIN` | yes | The Vercel address, no trailing slash |
| `CONTENT_ORIGIN` | yes | The content service address |
| `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | yes | File storage |
| `ENVIRONMENT` | yes | `production` (already in the Blueprint) |
| `PROXY_HOPS` | API | Number of proxies adding to `X-Forwarded-For`. On Render, `2` (Render's edge and its proxy; already in the Blueprint) |
| `RATE_LIMIT_ENABLED` | API | `true` by default. Turn off only for load tests |
| `RETENTION_ENABLED` | API | `true` by default |
| `WEBHOOK_WORKER` | API | `true` by default |
| `EMAIL_BACKEND`, `SMTP_*`, `EMAIL_FROM` | API | `console` only logs invitation emails. Use `smtp` to send them |

Never set `WEBHOOK_ALLOW_PRIVATE` in production.

The API start command applies database migrations before it starts, so a deploy that includes
a migration needs no extra step. The health check is `/healthz`; `/readyz` also checks the
database.

Set `PROXY_HOPS` carefully. Render's edge adds the caller's address and then its own, so the caller is second from the right. This was true at the time of writing; after deploying, check a request log if you depend on per address limits. If it is 0 behind a proxy, every caller shares one rate limit.
If it is larger than the real number of proxies, callers can choose their own address.

## 4. Frontend on Vercel

Import the repository with the `frontend` folder as the root. Set:

| Variable | Value |
| --- | --- |
| `BACKEND_URL` | The API address on Render |
| `NEON_AUTH_BASE_URL` | The same value as `NEON_AUTH_URL` |
| `NEON_AUTH_COOKIE_SECRET` | A random string of 32 or more characters |

The frontend forwards `/api/*` to the API, so people and the CLI can use the Vercel address.

## 5. Check it

1. Open the frontend, sign up, and choose a handle.
2. Create a token in Settings and run `paddock login` then `paddock deploy` (see `cli/README.md`).
3. Open the page, leave a comment with `@agent`, and watch it arrive with `paddock watch`.

## Running with Docker instead

`backend/Dockerfile` builds one image for both services. It runs as a non root user.

```
docker build -t paddock-backend backend

# API (applies migrations first)
docker run -p 8000:8000 --env-file backend/.env paddock-backend

# Content service
docker run -p 8001:8001 --env-file backend/.env paddock-backend \
  uvicorn app.content:app --host 0.0.0.0 --port 8001
```

With `STORAGE_BACKEND=local` mount a volume at `/data`. The file storage must be shared by both
containers, so for anything but a single machine use S3 storage. The image has not been built
in the environment where this guide was written (no Docker there), so run the build once and
check the health command before relying on it.

## Upgrades

1. Merge to `main`. Render redeploys both services; the API runs migrations on start.
2. Migrations are written to be applied before the new code runs. If one is not backwards
   compatible, say so in the pull request and deploy in two steps.
3. The frontend redeploys on Vercel by itself.

## Backups

- Neon keeps history for point in time restore (window depends on your plan). Check it covers
  the time you need.
- Files in the bucket: turn on versioning or a lifecycle rule at your storage provider.
  Retention only deletes files that no version uses and that are over 7 days old.
- A page removed by a person is kept for 30 days before it is removed for good.

## Retention

A job removes old data once a day in the API process (first run five minutes after start).
Run it by hand with `python -m app.jobs retention`. What it removes: events and delivery history
older than 30 days, ended invitations and links older than 30 days, pages deleted over 30 days
ago, files no version uses for 7 days, and audit entries over a year old.

## Rotating secrets

| Secret | How |
| --- | --- |
| `SECRET_KEY` | Change on both services together. Webhook secrets are encrypted with a key derived from it, so existing webhooks must be deleted and created again |
| Storage keys | Create a new key, set it on both services, delete the old key |
| Database password | Reset in Neon, update both connection strings on both services |
| `NEON_AUTH_COOKIE_SECRET` | Change in Vercel. People are signed out once |
| An agent token | Revoke it in Settings and create a new one |

## Scaling notes

Run one API instance. The rate limiter, live event hub and retention loop are in memory. To
run more, move the limiter and hub to Redis and run retention as a scheduled job. The content
service holds no state and can run as many copies as needed.

## Load test

`backend/scripts/loadtest.py` reads a few endpoints with an agent token and reports requests
per second and latency. Start the API with `RATE_LIMIT_ENABLED=false` first.

```
python backend/scripts/loadtest.py --url http://localhost:8000 --token pdk_... --seconds 20 --workers 20
```

Result from the review (one API process, local Postgres, 20 workers, 20 seconds): 5092
requests, about 254 per second, no errors, p95 under 140 ms for every endpoint. This ran on a
shared development machine with the database next to the API, so treat it as a smoke test.
Real numbers on Render and Neon will be higher in latency, and the free Render plan will be
the limit long before the code is.
