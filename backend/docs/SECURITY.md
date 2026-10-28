# Paddock: security review

This is the review done at the end of milestone 9. It walks through the security list in
`ARCHITECTURE.md` section 6, says what the code does today, and lists what is still open.
The date of the review is 28 October 2026.

## Summary

| Area | Status |
| --- | --- |
| Untrusted page code | Done: separate origin, sandboxed frame, strict policy |
| Authentication | Done: Neon Auth tokens for people, hashed scoped tokens for agents |
| Authorisation | Done: one policy module, checked in tests |
| Uploads | Done: size, count and path limits, traversal blocked |
| Abuse controls | Done for one instance: rate limits and body cap |
| Webhooks | Done: signed, address checked and pinned |
| Secrets | Done: encrypted at rest where stored, never logged |
| Dependencies | Clean at review time (see below) |
| Multi instance scaling | Open: rate limits and live events are in memory |

## Checklist against the architecture

### 1. Separate content origin

Published pages are served by a second app (`app.content`) on its own address. The dashboard
and API never serve page files. In the live setup the content service runs on a different
registrable domain from the frontend, so the browser keeps cookies and storage apart.

### 2. Sandboxed frames

The frontend embeds a page in an iframe with the `sandbox` attribute. Scripts are allowed,
but the page does not get the dashboard's origin.

### 3. Content security policy

Every content response carries:

- `Content-Security-Policy` that allows only same origin scripts, styles and connections,
  `form-action 'none'`, `base-uri 'none'`, and `frame-ancestors` limited to the app origin
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `Cross-Origin-Resource-Policy: same-site`
- `X-Robots-Tag: noindex, nofollow`

Known trade off: `script-src` and `style-src` allow `'unsafe-inline'`, because agents publish
single file pages with inline scripts. The page cannot reach the network (`connect-src 'self'`)
and cannot reach the dashboard origin, which is what limits the damage. Images may load from
any https address, which means a page can send data out through an image address. That is
accepted for now and should be revisited if pages ever receive private data.

### 4. No credentials on the content origin

Content links are short lived signed addresses (15 minutes by default). The content service
never receives a sign in token or an agent token.

### 5. Token hygiene

- People sign in through Neon Auth. The API checks the signed token against Neon's published
  keys and requires a verified email where configured. Passwords are never seen by Paddock.
- Agent tokens start with `pdk_`, are random, are stored only as a SHA-256 hash, are shown once
  and can be revoked. Each token has scopes and an optional expiry. A token cannot do anything
  its owner could not do.
- Webhook secrets are shown once and stored encrypted (Fernet, key derived from `SECRET_KEY`).

### 6. Upload validation

The size of the whole bundle, the size of each file, the file count and every path are checked.
Paths with `..`, absolute paths and unusual characters are refused. Requests whose declared
body is far over the limit are refused before the body is read (413).

### 7. Authorisation on every query

All access decisions live in `app/core/policy.py`. Handlers ask the policy module; they do not
decide themselves. Pages the caller cannot see answer 404, not 403, so their existence does
not leak. Events are filtered per subscriber by a database check on every delivery, and
member changes are visible only to the page owner.

### 8. Abuse controls

Fixed one minute windows, per credential (hashed Authorization header) or per IP when there is
no credential:

| Rule | Calls per minute |
| --- | --- |
| General, any credential | 600 |
| Anonymous, per IP | 120 |
| Publish (create, new version, restore) | 30 |
| Comments | 60 |
| Requests (claim, complete, dismiss) | 120 |
| Manage (tokens, webhooks, invites, links) | 20 |
| Live streams opened | 30 |
| View links | 120 |

Answers are `429` with `Retry-After`. The `paddock` CLI waits and retries.

`PROXY_HOPS` must match the number of proxies that add to `X-Forwarded-For`. Too low and all
callers share the proxy's address. Too high and a caller can write their own address. The
default is 0, which ignores the header.

Other API responses carry `X-Content-Type-Options`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer` and `Cache-Control: no-store`, plus HSTS in production.
Public link pages are not indexed by search engines.

### 9. Webhook safety

- Every delivery is signed: `X-Paddock-Signature: v1=<HMAC SHA-256 of "timestamp.body">`.
  Receivers should reject old timestamps.
- Addresses must be https and must not resolve to private, loopback, link local or reserved
  networks. This is checked when the webhook is saved and again when each delivery is sent.
- The connection is pinned to the address that was checked (the request goes to that IP, with
  the original host name for the certificate and the Host header), so a host name that changes
  its answer between the check and the connection cannot reach an internal address.
- Redirects are not followed.
- A user may have 10 webhooks. Failed deliveries are retried on a fixed schedule and then
  given up.

## Other findings

- **Errors.** Error bodies use a fixed shape with a request id. Stack traces are not returned.
- **Logs.** Tokens, secrets and request bodies are not logged. Slow requests are logged with
  the path and time only.
- **CORS.** Only `APP_ORIGIN` is allowed.
- **Production guards.** The app refuses to start in production with the development secret or
  without `NEON_AUTH_URL`.
- **Retention.** Old events, delivery history, ended invitations and links, deleted pages and
  unused files are removed daily, so data does not stay forever. See the backend README.
- **Container.** The Docker image runs as a non root user and holds no secrets.

## Dependency audit

`pip-audit` was run on the 34 packages pinned in `uv.lock` (production only). Result: no known
vulnerabilities. Repeat this before each release:

```
cd backend
uv export --frozen --no-dev --no-hashes --no-emit-project > /tmp/req.txt
pip-audit -r /tmp/req.txt --no-deps --disable-pip
```

## Open items and limits

1. **Single instance.** The rate limiter, the live event hub and the retention loop live in the
   API process. Run one API instance. For more, move the limiter and hub to Redis and run
   retention as a scheduled job (`python -m app.jobs retention`).
2. **Event ordering.** Event ids follow commit order closely but not perfectly when two
   transactions overlap. A client that reconnects with `Last-Event-ID` could, rarely, miss an
   event written by a slower transaction. Pages refetch on `resync`, so the screen heals.
3. **Free host sleep.** On Render's free plan the API sleeps when idle. Streams drop and are
   resumed by the client; webhook retries resume when the process wakes.
4. **Unused file race.** If retention removes a file at the exact moment a publish reuses it,
   the publish fails with an error and can be repeated. Nothing is corrupted.
5. **Inline scripts and image loading** in published pages, as described above.
6. **No two factor sign in** until Neon Auth offers it for this setup.
7. **No external penetration test** has been done. This is a code and configuration review.
