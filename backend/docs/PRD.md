# Paddock: Product Requirements Document (v1)

Status: Draft for review
Owner: Swapnil Bhattacharya
Scope of this release: Backend (Python). The frontend (Next.js) is built in step with the backend: the first release (landing, accounts, tokens) is done, and each later backend milestone gets its screens.

## 1. Summary

Paddock is a hosted workspace where people and their own AI agents publish, read, discuss and improve pages together. An agent (Claude Code, Codex, Cursor or any tool that can run a command or call an HTTP API) publishes a page, such as a report, dashboard, mockup or small app, to a private URL. People open the page, comment on it, and mention the agent to request changes. The agent receives the request in real time, improves the page, and publishes a new version. Every version is kept.

Paddock is inspired by the concept of Spacesheep (spacesheep.dev). It is an original product with its own name, branding, copy and visuals. No assets, text or marks are copied.

## 2. Guiding principle: bring your own agent

Paddock never calls a language model. It stores no model keys, runs no inference and builds no prompts. All intelligence lives in the agents that users connect. Paddock is the hosting, versioning, collaboration and notification layer.

Consequences:
- No inference cost or model-provider dependency for Paddock.
- The agent is a client of the Paddock API, authenticated with a user-created API token.
- A revision request is plain data (a comment with an @agent mention). Any agent can act on it.

## 3. Goals and non-goals

### Goals (v1)
1. Let any agent publish a page (single file or folder with scripts and images) and publish new versions of it.
2. Keep every version, and allow viewing and rolling back to any of them.
3. Serve pages safely at private URLs with sharing controls.
4. Let people comment on a page or on a specific part of it.
5. Turn an @agent mention into an open revision request that agents learn about in real time.
6. Push all changes in real time to browsers, agent CLIs and optional webhooks. No polling is required for any v1 flow.
7. Ship a backend that is complete, tested, documented and deployable, so the frontend can be built against it.

### Non-goals (v1)
- Any built-in AI or model integration.
- Live data streams from machines or services.
- Full-text or semantic search across pages.
- Sync to Google Drive or GitHub.
- Document signing and the browser extension.
- Billing, plans and organisation-wide administration.
- Native mobile apps.

These may follow in later versions.

## 4. Users

| User | Description | Main need |
|---|---|---|
| Owner | A person who connects an agent and publishes pages | Publish easily, control who sees pages |
| Collaborator | A teammate invited to a page | Read, comment, request changes |
| Agent | A program acting for an owner via an API token | Publish versions, read comments, act on requests |

## 5. User stories

Accounts and tokens
- As an owner, I can sign up, log in and log out.
- As an owner, I can create, name, scope and revoke API tokens for my agents.

Publishing
- As an agent, I can publish a page from a single HTML file or a folder containing HTML, scripts and images.
- As an agent, I can publish a new version of an existing page.
- As an owner, I can list my pages, view any version, and roll back to an earlier version.
- As an owner, I can delete a page.

Sharing
- As an owner, I can keep a page private, invite specific people with a role (viewer, commenter, editor), or create a link that anyone can open.
- As an owner, I can revoke any invitation or link.

Comments and requests
- As a collaborator, I can comment on a page, anchor a comment to a part of the page, reply in a thread, and resolve a thread.
- As a collaborator, I can write @agent in a comment to create a revision request.
- As an agent, I can see open requests for pages I may edit, claim one so others do not duplicate the work, post a reply, and mark it done with the version I published.

Real time
- As a viewer, I see new comments, versions and request status changes instantly, without refreshing.
- As an agent, I can keep a live connection open and receive each new request the moment it is created.
- As an owner, I can register a webhook to receive signed events on a public server.

## 6. Functional requirements

IDs are used for traceability in the SDD and tests.

| ID | Requirement |
|---|---|
| F-01 | Email and password sign up, login, logout, with secure password hashing. |
| F-02 | API tokens with a visible prefix, hashed at rest, shown once, with scopes and revocation. |
| F-03 | Create a page with a title, slug and initial version from an uploaded bundle. |
| F-04 | A bundle is a single file or a folder. It may contain HTML, CSS, JavaScript, images and fonts, within size and type limits. |
| F-05 | Each publish creates an immutable version with a number, author (user or token) and optional message. |
| F-06 | Roll back by publishing an earlier version as the newest version (history is never rewritten). |
| F-07 | Pages are served from a separate content origin, with a strict content security policy. |
| F-08 | Visibility: private, invited members, or anyone with the link. |
| F-09 | Roles: viewer, commenter, editor. Owner has all rights. |
| F-10 | Comments with replies, optional anchors, edit, delete and resolve. |
| F-11 | A comment containing the @agent mention creates a revision request linked to that comment and the page version it was written against. |
| F-12 | Revision request states: open, claimed, done, dismissed. Claims expire if the agent goes silent. |
| F-13 | A page can list its open requests through the API. |
| F-14 | Real-time event stream per page and per user, over server-sent events, with replay from the last seen event. |
| F-15 | Optional signed webhooks with retries. |
| F-16 | A command line tool: login, deploy, watch, comments, reply, versions. |
| F-17 | Every endpoint documented in an OpenAPI schema. |
| F-18 | Audit trail of publishes, shares, token use and deletes. |

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Security | Untrusted scripts must not be able to read another user's session or data. See ARCHITECTURE.md section 6. |
| Performance | Event delivery to a connected client within 1 second under normal load. Page serving cached at the edge when possible. |
| Reliability | No lost events: a client that reconnects receives everything it missed. |
| Cost | Runs on free tiers for development and early use (Neon free plan, free object storage). |
| Portability | Storage and event layers sit behind interfaces so providers can be swapped. |
| Quality | Automated tests for all rules in this document. Migrations are versioned. |
| Observability | Structured logs, request IDs and a health endpoint. |

## 8. Success measures for v1

1. An agent can go from a new token to a published page in under five minutes using only the CLI and the setup guide.
2. A comment containing @agent reaches a watching agent in under one second.
3. A published page with scripts and images cannot access cookies or data of the Paddock dashboard origin.
4. All requirements in section 6 have passing automated tests.

## 9. Constraints and decisions already made

- Backend language and framework: Python with FastAPI.
- Database: Neon serverless Postgres, free plan. The project was created in AWS US East 2 (Ohio). A region cannot be changed after creation.
- Files: object storage behind an interface. Local disk in development. Neon object storage or Cloudflare R2 in production, to be confirmed.
- No polling. Real-time delivery is by server-sent events, with optional webhooks.
- Frontend: Next.js, built after the backend ships.

## 10. Open questions

1. Public link pages: allow indexing by search engines, or always block it? (Proposed default: block.)
2. Content domain: which domain will serve user pages in production? A separate registrable domain is the safest option.
3. Maximum bundle size and file count for the free tier. (Proposed: 25 MB per bundle, 200 files.)
4. Should the first release include organisations and teams, or only individual accounts with invited members? (Proposed: individual accounts only.)
5. Object storage provider for production, after Neon object storage maturity is confirmed.
