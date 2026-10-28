# One-step agent connection (MCP with sign-in)

Date: 2026-10-28
Status: draft for review
Branch: one-step-connect (stacked on ui-revamp)

## 1. Goal

A person with no technical background connects Claude Desktop, ChatGPT desktop, Claude Code or Codex to Paddock in one or two steps, without copying a token.

What the person does:

1. Paste one address (or one command) into their tool.
2. Click Allow in the browser tab that opens.

Success means: after those two steps, the agent can publish pages, read comments and act on requests for that person, and the person can see and revoke the connection in Settings.

Constraints:

- Works for any tool that speaks MCP over HTTP with OAuth (the four named tools, plus Cursor and Grok for free).
- The existing token connection stays, now labelled Advanced.
- Paddock still runs no model. The agent is always the user's own.
- Reuse the existing token, scope and role rules. No second permission system.

Out of scope for this version: refresh tokens, social login, MCP resources and prompts, Windsurf key setup, and an in-app agent.

## 2. How it works

One address for all tools: `https://<api-host>/mcp`. The address points at the API host directly (not the Vercel site), because OAuth discovery paths must sit at the host root.

Flow, with the standard MCP authorization steps:

1. The tool calls `/mcp` with no token. The API answers 401 with a `WWW-Authenticate` header naming the protected resource metadata URL.
2. The tool reads `/.well-known/oauth-protected-resource`, then `/.well-known/oauth-authorization-server`.
3. The tool registers itself at `POST /oauth/register` (dynamic client registration) and gets a `client_id`.
4. The tool opens the browser at `GET /oauth/authorize` with PKCE (S256) and the redirect address it registered.
5. The API validates the request and redirects to the frontend page `/oauth/consent`, carrying the original, already validated query parameters. Approval re-validates everything, so nothing in that URL is trusted.
6. The person logs in if needed, sees who is asking and what it may do, and clicks Allow or Deny.
7. The frontend calls `POST /v1/oauth/approve` as the signed-in person. The API returns the redirect URL carrying a single-use code. Deny returns `error=access_denied`.
8. The tool calls `POST /oauth/token` with the code and the PKCE verifier and receives an access token.
9. The access token is an ordinary Paddock agent token (`pdk_...`). The tool uses it as a Bearer token on `/mcp`.

No refresh tokens. The access token does not expire. Revoking it in Settings makes the next call fail with 401, and the tool shows its normal "sign in again" prompt.

## 3. Components

### 3.1 OAuth endpoints (backend, `app/api/oauth.py`, `app/services/oauth.py`)

| Endpoint | Purpose |
| --- | --- |
| `GET /.well-known/oauth-protected-resource` and `/mcp` variant | Metadata that names the resource and the authorization server |
| `GET /.well-known/oauth-authorization-server` | Metadata: endpoints, `S256`, `none` client auth, `authorization_code`, scopes |
| `POST /oauth/register` | Dynamic client registration, rate limited per IP |
| `GET /oauth/authorize` | Validates the request, redirects to the consent page |
| `POST /v1/oauth/preview` | Signed-in person only. Returns the client name, redirect host and scopes for the consent page |
| `POST /v1/oauth/approve` | Signed-in person only. Creates the code or the deny redirect |
| `POST /oauth/token` | Exchanges code plus verifier for the access token |

Rules:

- PKCE with S256 is required. Plain is refused.
- Redirect address must exactly match one registered, with one exception: for `http` loopback addresses (`localhost`, `127.0.0.1`, `[::1]`) the port may differ (RFC 8252), because Claude Code and Codex choose a free port at run time. Allowed addresses: `https`, `http` on loopback, and private-use custom schemes (at least 3 characters, not `javascript`, `data`, `file`, `vbscript`, `blob`, `about`, and not `http`) so Cursor works.
- Codes are random, stored hashed, valid for 10 minutes and usable once. A second use revokes the token it produced.
- The `resource` parameter, if sent, must equal our MCP address.
- Scopes offered: `pages:read pages:write comments:read comments:write requests:act`. `events:read` is not offered.
- A person who re-authorizes the same client gets a new token and the older OAuth token for that client is revoked, so Settings does not fill up.

### 3.2 Data (migration `0008_oauth.py`)

- `oauth_clients`: `id`, `client_id` (unique), `client_name`, `redirect_uris` (JSON list), `created_at`, `last_used_at`.
- `oauth_codes`: `code_hash` (unique), `client_id`, `user_id`, `redirect_uri`, `code_challenge`, `scopes`, `expires_at`, `used_at`, `token_id` (nullable, the token the code produced, so reuse can revoke it).
- `api_tokens`: add nullable `client_id` and a `source` column (`manual` or `oauth`). Existing rows become `manual`.
- Retention loop deletes expired codes and clients unused for 30 days that have no live token.

### 3.3 MCP server (backend, `app/mcp/`)

Built with the official Python MCP library in resource-server mode, mounted in the FastAPI app at `/mcp`, stateless (no sessions held in memory, so restarts and the sleeping free tier do no harm).

- A token verifier looks up the Bearer token with the existing `tokens.find` and returns the user and scopes.
- Each tool calls the same service functions the REST routes use, so roles, scopes, rate limits and audit entries stay identical.

Tools (names are stable, wording is plain):

| Tool | Does |
| --- | --- |
| `list_pages` | Pages the person can open |
| `get_page` | A page with its latest files as text |
| `publish_page` | Create a page or add a version. Files given as `{path, content}`, with `encoding: "base64"` for images |
| `list_comments` | Comments on a page |
| `reply_to_comment` | Reply in a thread |
| `list_requests` | Open revision requests |
| `claim_request` | Claim one |
| `complete_request` | Finish with a reply and the version that fixed it |

Large files: the body cap that already protects the API applies. Tool errors return a clear message the agent can act on.

### 3.4 Frontend

- New page `/oauth/consent`: shows the app name, the host it will return to, and a short list of what Allow means in plain words. Buttons Allow and Deny. If the person is signed out, it sends them to login and back. Keyboard and screen reader friendly like the rest of the site.
- Redesigned `/connect` page:
  - Tabs: Claude Desktop, ChatGPT, Claude Code, Codex.
  - Each tab shows the address or one command with a Copy button and three numbered plain steps.
  - A live "Connected" badge per tool, from the person's token list (tokens with `source = oauth` and the client name).
  - The existing token flow moves under "Advanced".
  - Calls the existing wake-up request before showing the address, to avoid first-connection timeouts on the sleeping free tier.
- Settings, Tokens: show connection name, "Connected with sign-in" label, last used, Revoke.

### 3.5 Cross-origin

OAuth and MCP routes allow any origin without cookies (they use Bearer tokens and PKCE), so browser-based clients work. The consent approval call comes from our frontend through the existing proxy.

Settings: `API_PUBLIC_URL` on the backend (the API's public origin, issuer and MCP host) and `NEXT_PUBLIC_MCP_URL` on the frontend (the full MCP address shown on the Connect page).

## 4. Security

- Open dynamic registration is required by the tools, so abuse is limited by: per-IP rate limit, exact redirect matching, PKCE, single-use short codes, no secrets in clients, and consent that names the return host.
- The consent page is the only place a person grants access, and only a signed-in person with a verified email can approve (agent tokens cannot).
- An audit log entry is written for registration, approval, denial and revocation.
- Tokens are shown to nobody. They travel only from `/oauth/token` to the tool.
- Not stored: client secrets (public clients only).

## 5. Errors

- Bad or expired code, wrong verifier, reused code: standard OAuth error JSON.
- Denied: redirect with `error=access_denied`.
- Unverified email: consent page tells the person to verify first.
- Revoked token: 401 from `/mcp`, with the metadata hint so the tool can sign in again.

## 6. Testing

- Backend unit and API tests: registration rules, redirect matching, PKCE failure, code reuse, expiry, approve and deny, token issue, revoke on re-authorize, scope limits, MCP tools through the stand-in client.
- A stand-in MCP client script that runs the whole flow (discovery, register, authorize, approve, token, tool calls) against a local server, used in CI.
- Frontend: consent page and Connect page checked with the same accessibility, contrast and interaction scripts used for the UI work, light and dark, desktop and phone.
- A manual checklist for the real apps (Claude Desktop, ChatGPT, Claude Code, Codex), because I cannot run those from here.

## 7. Risks and open items

- Real-app behaviour: each tool has quirks. Mitigation is the manual checklist and fixing what it finds.
- ChatGPT needs Developer mode on Pro or Plus. Claude Desktop custom connectors may depend on plan. The Connect page will say so plainly.
- The free tier sleeps. The wake-up call helps, but a very cold start may still need one retry. The page says so.
- Render must serve the API at a stable public host for the address to stay valid. Changing the host means reconnecting.

## 8. Decisions made

- Our API is the authorization server (approach A).
- Access tokens are ordinary agent tokens, no expiry, no refresh.
- Official MCP library for the protocol layer only.
- One address for every tool.
