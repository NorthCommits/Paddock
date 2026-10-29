# One-step agent connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person connects Claude Desktop, ChatGPT, Claude Code or Codex to Paddock by pasting one address and clicking Allow, with no token copied.

**Architecture:** The FastAPI backend becomes an OAuth 2.1 authorization server for public clients (dynamic registration, PKCE S256, single-use codes) and hosts an MCP endpoint at `/mcp`. The access token issued is an ordinary `pdk_` agent token, so all existing scope and role checks apply. The Next.js frontend adds a consent page and a redesigned Connect page.

**Tech Stack:** FastAPI, SQLAlchemy 2 (async), Alembic, the official `mcp` Python library (resource-server mode), pytest, Next.js 16, React 19, SWR, Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-10-28-one-step-agent-connect-design.md` (amended in Task 0 below).

## Global Constraints

- Backend lives in `backend/`; tests run with `cd backend && uv run pytest`. Lint with `uv run ruff check .`. Line length 100, Python 3.12.
- Frontend lives in `frontend/`; check with `npx tsc --noEmit`, `node scripts/check-contrast.mjs`, and the axe scripts. No emojis and no em dashes in code, copy or docs.
- Scopes offered through OAuth: `pages:read pages:write comments:read comments:write requests:act`. Never `events:read`.
- PKCE method `S256` only. Codes valid 10 minutes, single use, stored only as sha256 hashes. Tokens never expire and are never shown.
- OAuth and MCP routes live at the API host root: `/.well-known/oauth-protected-resource`, `/.well-known/oauth-protected-resource/mcp`, `/.well-known/oauth-authorization-server`, `/oauth/register`, `/oauth/authorize`, `/oauth/token`, `/mcp`. The person-only routes are `POST /v1/oauth/preview` and `POST /v1/oauth/approve`.
- New settings: `API_PUBLIC_URL` (the API's public origin, used as the issuer and MCP resource host; default `http://localhost:8000`). The consent page lives at `{APP_ORIGIN}/oauth/consent`.
- Frontend env: `NEXT_PUBLIC_MCP_URL` (full MCP address shown on the Connect page; default `http://localhost:8000/mcp`).
- Rate limit rule `register`: 20 per minute per IP. Use existing `manage` for approve and `general` for the rest.
- Do not commit env files or secrets. Commit identity for this repo: `git -c user.name="Swapnil Bhattacharya" -c user.email="swapnil.bhatt17@outlook.com"`. End commit messages with the Co-Authored-By and Claude-Session lines supplied for this session.
- Work on branch `one-step-connect`. Nothing is pushed or deployed; the user does that.

## Review Focus

1. Redirect address that differs from a registered one (trailing slash, extra query, other host, other port on a non-loopback address): refused, never redirected to. A different port on a loopback address is allowed.
2. Authorization code used twice: the second use fails and the token it produced stops working.
3. Person clicks Deny: the client gets `error=access_denied` and no token exists.
4. Revoked token calling `/mcp`: a clean 401 with the metadata hint, never a 500.
5. Same person authorizes the same client twice: exactly one live OAuth token remains.
6. Person with an unverified email approving: refused with the existing "verify your email" message.
7. `publish_page` with bad base64, a huge file or a bad path: a clear error message, not a crash.

---

### Task 0: Amend the spec

**Files:** Modify `docs/superpowers/specs/2026-10-28-one-step-agent-connect-design.md`

- [ ] **Step 1:** Edit the spec to match these decisions made while planning: (a) the authorize endpoint validates then redirects to the consent page carrying the original, already validated query parameters (no signed reference); approve re-validates everything; (b) add `POST /v1/oauth/preview` returning client name, redirect host and scopes for the consent page; (c) loopback redirects ignore the port when matching, and redirect rules also allow private-use custom schemes (at least 3 characters, not `javascript`, `data`, `file`, `vbscript`, `blob`, `about`, and not `http`) so Cursor works; (d) `oauth_codes` gains a nullable `token_id` so reuse can revoke the issued token; (e) settings `API_PUBLIC_URL` and frontend `NEXT_PUBLIC_MCP_URL`.
- [ ] **Step 2:** Commit: `git add docs && git commit -m "Amend the connection spec with planning decisions"`.

### Task 1: Dependency, settings, migration and models

**Files:**
- Modify: `backend/pyproject.toml` (add `mcp` to dependencies; run `uv lock`), `backend/app/core/config.py`, `backend/app/db/models.py`
- Create: `backend/migrations/versions/0008_oauth.py`
- Test: `backend/tests/test_migrations.py` (extend), `backend/tests/test_oauth_models.py`

**Interfaces:**
- Produces: `Settings.api_public_url: str`; models `OAuthClient(id, client_id: str unique, client_name: str, redirect_uris: list[str], created_at, last_used_at)`, `OAuthCode(id, code_hash: str unique, client_id: str, user_id, redirect_uri: str, code_challenge: str, scopes: list[str], expires_at, used_at, token_id: UUID | None)`; `ApiToken.client_id: str | None`, `ApiToken.source: str` (`"manual"` default, or `"oauth"`).

- [ ] **Step 1: Write failing test** `test_oauth_models.py::test_oauth_tables_and_token_columns_exist`: create a user, an `OAuthClient`, an `OAuthCode`, and an `ApiToken` with `source="oauth"`, `client_id` set; commit; assert default `source == "manual"` when omitted.
- [ ] **Step 2:** Run `uv run pytest tests/test_oauth_models.py -v`; expect FAIL (import error).
- [ ] **Step 3:** Add the models and settings field (`api_public_url`, default `http://localhost:8000`, env `API_PUBLIC_URL`). Write migration 0008 that creates both tables, adds the two token columns (existing rows get `source='manual'`), and indexes `oauth_codes.expires_at`.
- [ ] **Step 4:** Extend `test_migrations.py` so its upgrade and downgrade round trip covers 0008. Run both test files; expect PASS.
- [ ] **Step 5:** Run `uv run ruff check .` and commit: `Add OAuth tables and token source column`.

### Task 2: OAuth service (registration, redirect rules, codes, token exchange)

**Files:**
- Create: `backend/app/services/oauth.py`
- Modify: `backend/app/services/tokens.py` (let `create` accept `client_id: str | None = None, source: str = "manual"`)
- Test: `backend/tests/test_oauth_service.py`

**Interfaces:**
- Produces:
  - `OFFERED_SCOPES: tuple[str, ...]` (the five scopes)
  - `redirect_ok(uri: str) -> bool` (https; http on `localhost`, `127.0.0.1`, `[::1]`; private-use scheme rule from the spec)
  - `async register_client(db, *, client_name: str, redirect_uris: list[str]) -> OAuthClient` (raises `OAuthError("invalid_redirect_uri" | "invalid_client_metadata", description)` for empty list, more than 10 uris, uri over 500 characters, name over 100)
  - `async get_client(db, client_id: str) -> OAuthClient | None`
  - `check_request(client: OAuthClient, *, redirect_uri, code_challenge, code_challenge_method, scope: str | None, response_type) -> list[str]` returns the granted scopes; raises `OAuthError` (`invalid_request`, `unsupported_response_type`, `invalid_scope`) and requires exact string equality with a registered uri (the one exception: for http loopback addresses `localhost`, `127.0.0.1` and `[::1]` the port may differ, RFC 8252 section 7.3) and `S256`
  - `async approve(db, user, client, *, redirect_uri, code_challenge, scopes, ip) -> str` returns the raw code
  - `async exchange(db, *, client_id, code, code_verifier, redirect_uri, ip) -> tuple[str, list[str]]` returns raw token and scopes; raises `OAuthError("invalid_grant", ...)`
  - `class OAuthError(Exception)` with `code: str`, `description: str`
- Consumes: `tokens.create`, `security.new_secret`, `security.sha256_hex`, `audit.record`.

- [ ] **Step 1: Write failing tests** (one function each, using real DB fixtures like `test_tokens.py`): `test_redirect_ok_rules` (https yes, `http://localhost:33445/cb` yes, `http://evil.com/cb` no, `javascript:alert(1)` no, `cursor://anysphere.cursor/oauth` yes); `test_register_limits`; `test_check_request_requires_exact_redirect_and_s256` (trailing slash differs, `plain` refused, loopback port may differ but loopback path may not); `test_exchange_happy_path_creates_oauth_token` (token has `source == "oauth"`, `client_id` set, name is `"<client_name> (connected with sign-in)"` cut to 100 characters, no expiry); `test_code_is_single_use_and_reuse_revokes_token`; `test_code_expires_after_ten_minutes`; `test_wrong_verifier_or_redirect_fails`; `test_reauthorizing_same_client_leaves_one_live_token`.
- [ ] **Step 2:** Run `uv run pytest tests/test_oauth_service.py -v`; expect FAIL.
- [ ] **Step 3:** Implement. Approach: store `sha256(code)`; PKCE check is `base64url(sha256(verifier))` without padding compared with `security.same_value`; in `exchange`, load the code row `with_for_update`, if `used_at` is set revoke the token in `token_id` and raise `invalid_grant`; otherwise mark used, revoke the user's older live tokens with the same `client_id`, create the token through `tokens.create`, store `token_id`, and update `client.last_used_at`. Audit `oauth.register`, `oauth.approve`, `oauth.token`.
- [ ] **Step 4:** Run the tests; expect PASS. Run the whole `tests/test_tokens.py` to confirm `tokens.create` still behaves.
- [ ] **Step 5:** Commit: `Add the OAuth service`.

### Task 3: OAuth HTTP endpoints and metadata

**Files:**
- Create: `backend/app/api/oauth.py`, `backend/app/schemas/oauth.py`
- Modify: `backend/app/main.py` (include routers; add a CORS rule so paths starting `/oauth`, `/.well-known` and `/mcp` allow any origin without credentials), `backend/app/core/ratelimit.py` (add `"register": 20`), `backend/app/schemas/auth.py` (`TokenOut` gains `source: str`)
- Test: `backend/tests/test_oauth_api.py`

**Interfaces:**
- Produces HTTP routes exactly as in Global Constraints. JSON shapes:
  - `POST /oauth/register` body `{client_name, redirect_uris, ...}` returns 201 `{client_id, client_name, redirect_uris, token_endpoint_auth_method: "none", grant_types: ["authorization_code"], response_types: ["code"]}`
  - `GET /oauth/authorize` returns 302 to `{app_origin}/oauth/consent?` plus the original query, or 400 JSON `{"error", "error_description"}` when `client_id` or `redirect_uri` is invalid (never redirect then); other validation errors redirect to the client's redirect uri with `error` and `state`
  - `POST /v1/oauth/preview` (verified person) body `{client_id, redirect_uri, code_challenge, code_challenge_method, scope, response_type, state}` returns `{client_name, redirect_host, scopes: list[str]}`
  - `POST /v1/oauth/approve` body is the preview body plus `decision: "allow" | "deny"`; returns `{redirect_to: str}` with `code` and `state`, or `error=access_denied` and `state`
  - `POST /oauth/token` form-encoded `grant_type=authorization_code, code, code_verifier, redirect_uri, client_id`; returns `{access_token, token_type: "Bearer", scope}`; errors 400 `{"error", "error_description"}`
  - Metadata documents use `API_PUBLIC_URL` as issuer and resource, advertise `code_challenge_methods_supported: ["S256"]`, `token_endpoint_auth_methods_supported: ["none"]`, `grant_types_supported: ["authorization_code"]`, `scopes_supported` and `registration_endpoint`.
- Consumes: Task 2 service; `VerifiedPersonDep` from `app/api/deps.py`.

- [ ] **Step 1: Write failing tests** with names: `test_metadata_documents`, `test_register_then_authorize_redirects_to_consent`, `test_authorize_with_unknown_client_returns_400_and_never_redirects`, `test_authorize_with_unregistered_redirect_returns_400`, `test_approve_allow_returns_code_and_state`, `test_deny_returns_access_denied_and_no_token_exists`, `test_unverified_email_cannot_approve` (expects the existing `email_not_verified` code), `test_agent_token_cannot_approve`, `test_token_endpoint_full_flow_returns_pdk_token`, `test_token_endpoint_reused_code_fails_and_token_stops_working`, `test_cors_open_for_oauth_paths_but_not_for_v1`, `test_register_is_rate_limited` (enable the limiter the way `test_hardening.py` does).
- [ ] **Step 2:** Run `uv run pytest tests/test_oauth_api.py -v`; expect FAIL.
- [ ] **Step 3:** Implement routes. Approach: a small helper builds the consent redirect from validated params; `OAuthError` is turned into the JSON error shape by a local handler on the oauth router; metadata served as plain dicts.
- [ ] **Step 4:** Run the new tests and `uv run pytest -q`; expect PASS across the suite.
- [ ] **Step 5:** `uv run ruff check .` then commit: `Add the OAuth endpoints and metadata`.

### Task 4: MCP endpoint and tools

**Files:**
- Create: `backend/app/mcp/__init__.py`, `backend/app/mcp/server.py`, `backend/app/mcp/tools.py`
- Modify: `backend/app/main.py` (mount at `/mcp`, run the MCP session manager in `lifespan`)
- Test: `backend/tests/test_mcp.py`

**Interfaces:**
- Produces: `app/mcp/server.py` exposes `mcp_app` (ASGI app mounted at `/mcp`, stateless, so no session lives in memory); a token verifier class `PaddockTokenVerifier` whose `verify_token(token: str)` uses `tokens.find` and returns the library's `AccessToken` (token, client_id, scopes) or `None`. `app/mcp/tools.py` registers these tools, each returning plain JSON-able dicts:
  - `list_pages(limit: int = 20)`, `get_page(page_id: str)` (latest files as text, base64 for binary), `publish_page(title: str, files: list[{path, content, encoding?}], page_id: str | None = None, message: str | None = None, entry_path: str | None = None)`, `list_comments(page_id: str, status: str | None = None)`, `reply_to_comment(page_id: str, comment_id: str, body: str)`, `list_requests(status: str | None = "open")`, `claim_request(request_id: str, minutes: int = 10)`, `complete_request(request_id: str, result_version: int, reply: str | None = None)`
  - Helper `async with acting_user() as (db, actor)` loads the caller via the library's current access token, builds `Actor(user, scopes, token)`, and applies `get_verified_actor` for write tools.
- Consumes: services `pages`, `comments`, `requests`, `bundles.check_bundle(IncomingFile list, entry_path, settings)`.

- [ ] **Step 1: Spike (read the installed library):** open the installed `mcp` package docs and source and write down in `backend/app/mcp/NOTES.md` (deleted at the end of this task) the exact names for: the server class, the auth settings, the Streamable HTTP app factory, the stateless option, the current-access-token helper, and how to set the HTTP path to `/` when mounted. The authorization doc is `https://py.sdk.modelcontextprotocol.io/run/authorization/`.
- [ ] **Step 2: Write failing tests** using the library's own client over an in-process ASGI transport, with names: `test_mcp_without_token_returns_401_with_metadata_hint` (header contains `resource_metadata=` and that URL returns 200), `test_mcp_with_revoked_token_returns_401_not_500`, `test_initialize_and_list_tools_shows_the_eight_tools`, `test_publish_page_creates_page_then_new_version`, `test_publish_page_rejects_bad_base64_with_clear_message`, `test_publish_page_rejects_oversize_file_and_bad_path`, `test_write_tool_without_pages_write_scope_is_refused`, `test_list_requests_claim_and_complete_round_trip`, `test_unverified_email_cannot_publish`, `test_mcp_works_without_trailing_slash_and_with_stateless_calls`.
- [ ] **Step 3:** Run `uv run pytest tests/test_mcp.py -v`; expect FAIL.
- [ ] **Step 4:** Implement. Approach: tools are thin wrappers that call the same service functions as the REST routes and translate `AppError` into tool errors carrying its message; `publish_page` decodes files into `IncomingFile`, runs `check_bundle`, then `pages.create` or `pages.publish`; metadata routes already exist from Task 3, so set the library's auth settings so its 401 header points at `{API_PUBLIC_URL}/.well-known/oauth-protected-resource/mcp`. If mounting at `/mcp` fights with FastAPI path handling, wrap the MCP ASGI app in a tiny route that forwards `/mcp` and `/mcp/` to it; keep the public address `/mcp`.
- [ ] **Step 5:** Run `uv run pytest -q` (whole suite) and ruff; expect PASS. Delete `NOTES.md`.
- [ ] **Step 6:** Commit: `Add the MCP endpoint and Paddock tools`.

### Task 5: Stand-in client end to end test and housekeeping

**Files:**
- Create: `backend/tests/test_oauth_flow_e2e.py`, `backend/scripts/mcp_standin.py`
- Modify: `backend/app/services/retention.py` (add `purge_oauth(db) -> int`, call it from `run()`), `backend/tests/test_retention.py`

**Interfaces:**
- Produces: `purge_oauth(db: AsyncSession) -> int` deletes expired or used codes older than one day and clients with no live token and no use for 30 days; `scripts/mcp_standin.py` runs the whole flow against a running local server and prints each step (discovery, register, authorize, approve using a given sign-in token, token, `list_pages`, `publish_page`).
- Consumes: everything from Tasks 2 to 4.

- [ ] **Step 1: Write failing tests:** `test_full_flow_discovery_to_publish` (follows 401 header to metadata to register to authorize to approve to token to an MCP `publish_page` call, then asserts the page exists via the REST API and the token shows in `GET /v1/tokens` with `source == "oauth"`); `test_purge_oauth_removes_old_rows_but_keeps_clients_with_live_tokens`.
- [ ] **Step 2:** Run; expect FAIL. **Step 3:** implement `purge_oauth` and the script. **Step 4:** run the suite; expect PASS.
- [ ] **Step 5:** Commit: `Add the end to end flow test, the stand-in client and cleanup`.

### Task 6: Consent page (frontend)

**Files:**
- Create: `frontend/src/app/oauth/consent/page.tsx`
- Modify: `frontend/src/lib/api.ts` (add `oauthPreview(body)` and `oauthApprove(body)` helpers using the existing authenticated fetch; add `source: string` to the token type)
- Test: interaction script `/tmp`-style playwright run (see Step 4)

**Interfaces:**
- Consumes: `POST /api/v1/oauth/preview` and `/approve` (through the existing proxy), the sign-in session helpers used by `(app)/layout.tsx`.
- Produces: route `/oauth/consent`. Reads the query parameters from Task 3, calls preview, shows client name, "You will return to {redirect_host}", a plain-words list of what Allow lets the app do (read and publish your pages, read and write comments, act on requests), and two buttons Allow and Deny. After approve it sets `window.location` to `redirect_to`. Signed-out visitors are sent to `/login?next=<this url>`. Unverified email shows the verify prompt. Uses `AuthLayout` for the look.

- [ ] **Step 1:** Build the page with loading, error ("This request looks wrong. Go back to your app and try again."), allow, deny and done states. Buttons are native buttons, focus moves to the heading on load, errors use `role="alert"`.
- [ ] **Step 2:** `npx tsc --noEmit` and `node scripts/check-contrast.mjs`; expect no output errors and "All colour pairs pass".
- [ ] **Step 3:** Run the dev servers (see `docs/DEPLOYMENT.md` for local start) against a local backend, register a client with curl, open `/oauth/consent?...` signed in, and click Allow; expect a redirect to the registered address carrying `code` and `state`. Click Deny on a second request; expect `error=access_denied`.
- [ ] **Step 4:** Run axe on the consent page in light and dark; expect 0 violations. Check phone width has no sideways scroll.
- [ ] **Step 5:** Commit: `Add the consent page`.

### Task 7: Connect page redesign and tokens list

**Files:**
- Modify: `frontend/src/app/(app)/connect/page.tsx`, `frontend/src/app/(app)/settings/tokens/page.tsx`, `frontend/.env.example`
- Create: `frontend/src/components/connect/tool-tabs.tsx`, `frontend/src/components/connect/connected-badge.tsx`

**Interfaces:**
- Produces: `ToolTabs` (props `{ mcpUrl: string; connectedNames: string[] }`) renders four tabs: Claude Desktop, ChatGPT, Claude Code, Codex, each with a Copy field and three plain numbered steps. Claude Desktop: Settings, Connectors, Add custom connector, paste the address, Connect. ChatGPT: turn on Developer mode, Create connector, paste the address, choose OAuth. Claude Code: `claude mcp add --transport http paddock <address>`, then `/mcp` and Authenticate. Codex: `codex mcp add paddock --url <address>`, approve in the browser. `ConnectedBadge` (props `{ connected: boolean }`) shows "Connected" with an icon and text, not colour alone. The page polls the token list with SWR every 3 seconds and treats a tool as connected when a token with `source === "oauth"` and a matching name prefix exists (`claude code`, `claude`, `chatgpt`, `codex`, case-insensitive, most specific first). The existing token flow and CLI section move under a collapsed "Advanced" disclosure. Before showing the address the page calls the existing wake-up request in `lib/warm.ts`. The Tokens settings rows show "Connected with sign-in" for `source === "oauth"`.
- Reads `process.env.NEXT_PUBLIC_MCP_URL` with fallback `http://localhost:8000/mcp`; add it to `.env.example`.

- [ ] **Step 1:** Implement the components and page changes. Mention plan limits in one line each: ChatGPT needs Developer mode on Pro or Plus; Claude Desktop custom connectors depend on plan.
- [ ] **Step 2:** `npx tsc --noEmit`, contrast check, axe on `/connect` and `/settings/tokens` in light and dark; expect 0 violations.
- [ ] **Step 3:** Interaction test: tabs switch with arrow keys, each Copy button puts the right text on the clipboard, completing the stand-in client flow flips the matching badge to Connected within 5 seconds, Revoke in Settings removes it. Check phone width.
- [ ] **Step 4:** Commit: `Redesign the Connect page around one-step sign-in`.

### Task 8: Docs, deployment settings and final verification

**Files:**
- Modify: `render.yaml` (add `API_PUBLIC_URL` as a variable the user fills in, `sync: false`), `docs/DEPLOYMENT.md` (new section: set `API_PUBLIC_URL` and `NEXT_PUBLIC_MCP_URL`, the address stays valid only while the API host does), `docs/SECURITY.md` (OAuth threat notes), `README.md` (one paragraph), `docs/MANUAL-CONNECT-CHECKLIST.md` (create: for each of the four real apps, the steps, the expected result, and what to report back)
- Test: none new

- [ ] **Step 1:** Write the docs. The checklist is the deliverable that lets the user try the real apps, because they cannot be run from the build environment.
- [ ] **Step 2:** Final verification: `uv run pytest -q`, `uv run ruff check .`, `npx tsc --noEmit`, contrast check, axe on `/`, `/login`, `/signup`, `/connect`, `/oauth/consent`; expect all pass and 0 violations.
- [ ] **Step 3:** Run the stand-in script against a local server and keep its printed output for the summary.
- [ ] **Step 4:** Commit: `Document one-step connection and add the manual checklist`. Do not push.
