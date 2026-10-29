# Presence and Page Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show who is on a page right now, and add a floating chat bubble for page-wide and private messages, without a second column.

**Architecture:** Two small Postgres tables (`page_presence`, `page_messages`) behind new routes. Live changes are pushed on the existing page stream as ephemeral events that are not written to the `events` table, so they never reach webhooks or agent tokens. The frontend adds a header avatar row and a floating bubble, driven by SWR plus the existing `useLive` hook.

**Tech Stack:** FastAPI, async SQLAlchemy 2, Alembic, pytest; Next.js 16, React 19, Tailwind v4, SWR.

**Spec:** `docs/superpowers/specs/2026-10-29-presence-and-chat-design.md`

## Global Constraints

- No emojis and no em dashes in code, comments, copy or docs.
- Keep code structure simple. Follow existing patterns (service in `app/services`, route in `app/api`, schema in `app/schemas`).
- Chat and presence are for people only. Agent tokens get 403 on every new route and receive none of the new events.
- Access uses `pages.role_for` and `pages.get_for_actor`. A stranger gets 404, never 403.
- Presence window is 45 seconds. Heartbeat every 20 seconds. Message body 1 to 1000 characters after stripping. Retention 30 days. Rate limit 20 messages per minute.
- Never commit secrets. Commit identity `Swapnil Bhattacharya <swapnil.bhatt17@outlook.com>` via `git -c user.name -c user.email`.
- Commit trailers: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01AguaV4tcuh4ibgi2kXDaaM`.
- Backend checks: `cd backend && .venv/bin/python -m pytest -q`, `ruff check .`, `ruff format --check .`. Frontend: `cd frontend && npx tsc --noEmit && node scripts/check-contrast.mjs`.

## Review Focus

- A removed member or someone on a now-private page keeps seeing chat or presence. Expected: 404 on routes and no live events at once.
- A page owner reading other people's private messages. Expected: impossible through any route.
- Private message to a person with no access to the page. Expected: 422, nothing stored.
- A private or page message reaching webhooks or an agent token stream. Expected: never.
- Two heartbeats at once, or a heartbeat after leave. Expected: one row, no error.
- Hidden tab or closed laptop keeps showing a person as here. Expected: gone within about 45 seconds.

---

### Task 1: Tables, policy, rate limit, and ephemeral live events

**Files:**
- Modify: `backend/app/db/models.py`, `backend/app/core/policy.py`, `backend/app/core/ratelimit.py`, `backend/app/services/events.py`, `backend/app/api/events.py`
- Create: `backend/migrations/versions/0012_presence_and_chat.py`
- Test: `backend/tests/test_live_chat_events.py`

**Interfaces:**
- Produces:
  - Models `PagePresence(page_id, user_id, last_seen_at)` with primary key on page and user, and `PageMessage(id uuid, page_id, sender_id, recipient_id nullable, body, created_at, deleted_at nullable)` with indexes on `(page_id, created_at)` and `recipient_id`. Both cascade on page delete, and `PageMessage.sender_id` cascades on user delete.
  - `events.push(page_id: uuid.UUID, type_: str, data: dict, audience: list[uuid.UUID] | None = None) -> None`. It publishes after the current session commits, and immediately if there is none. The item is `{"id": None, "type", "page_id", "created_at", "data", "owner": "", "people_only": True, "audience": [str ids] or None}`.
  - Policy action `"chat.write": ("viewer", "pages:read")`. Reads use the existing `page.view`.
  - Rate rule `"chat": 20`.
  - `events.stream(user_id, page_id, last_id, person: bool = True)`.

- [ ] **Step 1: Write failing tests in `test_live_chat_events.py`**
  - `test_push_item_has_no_id_and_is_not_stored`: call `events.push`, then count rows in `events` table is unchanged.
  - `test_frame_without_id_omits_the_id_line`: `events.frame({"id": None, "type": "message.created", ...})` has no line starting `id:`, and does not contain `audience` or `people_only`.
  - `test_stream_skips_people_only_for_agents`: drive `events.stream` with `person=False`, push an item, assert nothing is yielded within 0.2 s. With `person=True` and access, the frame is yielded.
  - `test_stream_respects_audience`: item with audience `[a]` is yielded to a, not to b (b has page access).
  - `test_stream_still_checks_access`: a person who loses access (page made private) gets no frame.
- [ ] **Step 2: Run them and confirm they fail** (`pytest tests/test_live_chat_events.py -q`).
- [ ] **Step 3: Implement** the models, migration 0012 (create both tables, down revision `0011`), policy action, rate rule, `events.push`, and the `stream` changes: for items with `id is None` skip the `seen` comparison and do not update `seen`; skip when `people_only` and not `person`; skip when `audience` is set and the user is not in it; keep the `can_see` check. In `frame`, drop `owner`, `people_only` and `audience`, and omit the `id:` line when id is None. In `api/events.py` pass `person=actor.is_person` through `_sse` for both routes.
- [ ] **Step 4: Run the new tests plus `test_events*.py` and confirm they pass.**
- [ ] **Step 5: Commit** `Add presence and chat tables and ephemeral live events`.

### Task 2: Presence service and routes

**Files:**
- Create: `backend/app/services/presence.py`, `backend/app/api/presence.py`, `backend/app/schemas/presence.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_presence.py`

**Interfaces:**
- Consumes: Task 1 models, `events.push`, `pages.get_for_actor`, `pages.role_for`.
- Produces:
  - `PRESENCE_SECONDS = 45`.
  - `presence.heartbeat(db, page, user) -> bool` upserts the row and returns True when the person was not here before (missing or older than the window).
  - `presence.leave(db, page, user) -> bool`.
  - `presence.here_ids(db, page_id) -> set[uuid.UUID]`.
  - `presence.people(db, page, viewer) -> list[PersonOut]` for everyone with access (owner plus members when the page is not private, owner only when private), each with `id, handle, display_name, here`.
  - `presence.has_here(db, page_id, user_id) -> bool` (used by Task 3).
  - Routes: `POST /v1/pages/{id}/presence` (204), `DELETE /v1/pages/{id}/presence` (204), `GET /v1/pages/{id}/people` (`{"items": [...]}`). Reads use `PersonDep` and action `page.view`; the heartbeat and leave use `VerifiedPersonDep` and the same action. Heartbeat joins push `presence.changed` with data `{"user_id", "here": true}`; leave pushes `here: false`.

- [ ] **Step 1: Write failing tests**
  - `test_heartbeat_marks_person_here_and_pushes_once`: first heartbeat returns joined and pushes an event; a second within the window does not push.
  - `test_person_disappears_after_45_seconds`: age `last_seen_at` by 46 seconds, `GET people` shows `here` false.
  - `test_leave_removes_and_pushes_false`.
  - `test_people_lists_owner_and_members_only_with_access`: private page lists only the owner; after sharing with members it lists the member too.
  - `test_stranger_gets_404_and_agent_token_gets_403` on all three routes.
  - `test_removed_member_gets_404`.
  - `test_parallel_heartbeats_keep_one_row` using `asyncio.gather` on two heartbeats.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** Use Postgres `insert ... on conflict do update` for the upsert. Compute `here` from rows newer than the window.
- [ ] **Step 4: Run the tests, ruff, and the full backend suite; confirm green.**
- [ ] **Step 5: Commit** `Add page presence`.

### Task 3: Chat messages, bell, retention

**Files:**
- Create: `backend/app/services/chat.py`, `backend/app/api/chat.py`, `backend/app/schemas/chat.py`
- Modify: `backend/app/main.py`, `backend/app/services/retention.py`
- Test: `backend/tests/test_chat.py`

**Interfaces:**
- Consumes: Tasks 1 and 2 (`events.push`, `presence.has_here`), `notifications.add(db, user_id, kind, *, page_id, request_id, actor_id, body)`, `pages.role_for`.
- Produces:
  - Schema `MessageOut(id, sender: {id, handle, display_name}, to: uuid | None, body, created_at, deleted: bool)`. Deleted messages have an empty body.
  - `chat.list_messages(db, page, user, with_id: uuid | None, before: datetime | None) -> tuple[list[MessageOut], bool]` (50 per call, oldest first, bool means more).
  - `chat.send(db, page, user, body: str, to: uuid | None) -> MessageOut`.
  - `chat.delete(db, user, message_id) -> None`.
  - Routes: `GET /v1/pages/{id}/messages?with=&before=`, `POST /v1/pages/{id}/messages` with `{"body", "to"?}` (201, rate rule `chat`), `DELETE /v1/messages/{id}` (204).
  - Events pushed after commit: `message.created` (audience `[sender, to]` for private, none for page) and `message.deleted`, with data `{"id", "to"}`.
  - Notification kind `chat_message`, created for a private recipient only when `presence.has_here` is false. Body is `"{display_name}: {first 80 characters}"`. No email.
  - Retention step `("messages", purge_old_messages)` deleting messages older than 30 days, and old presence rows older than 1 day.

- [ ] **Step 1: Write failing tests in `test_chat.py`** using `member` and `setup` helpers as in `tests/test_approvals.py`:
  - `test_viewer_can_read_and_write_everyone`.
  - `test_private_message_is_seen_only_by_the_two_people`, including that the page owner (a third person) gets an empty thread and cannot fetch it with `with=` either.
  - `test_private_message_to_a_person_without_access_is_422_and_not_stored`.
  - `test_removed_member_gets_404_and_stops_receiving`.
  - `test_body_is_trimmed_empty_and_over_1000_rejected` (422).
  - `test_sender_can_delete_own_and_owner_can_delete_in_everyone_but_not_private`.
  - `test_private_message_notifies_only_an_absent_recipient`: no `chat_message` notification when the recipient has a fresh heartbeat; one when not; never an email (assert no mail sent).
  - `test_message_events_do_not_reach_webhook_deliveries`: with an active webhook, no `webhook_deliveries` rows appear.
  - `test_agent_token_gets_403`.
  - `test_rate_limit_after_20_messages` (21st is 429).
  - `test_retention_deletes_messages_older_than_30_days`.
  - `test_pagination_returns_newest_50_oldest_first_and_more_flag`.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** Private thread query: `(sender = me and recipient = with) or (sender = with and recipient = me)`. `Everyone` is `recipient is null`. A `with` equal to the viewer's own id is 422. Push events only after commit by calling `events.push` once the commit has returned.
- [ ] **Step 4: Run the tests, ruff, and the full backend suite; confirm green.**
- [ ] **Step 5: Commit** `Add page chat`.

### Task 4: Frontend types, presence hook and avatar row

**Files:**
- Create: `frontend/src/components/presence-row.tsx`, `frontend/src/lib/presence.ts`
- Modify: `frontend/src/lib/api.ts`, `frontend/src/app/(app)/pages/[id]/page.tsx`

**Interfaces:**
- Produces:
  - Types in `api.ts`: `Person = {id, handle, display_name, here}`, `ChatMessage = {id, sender: {id, handle, display_name}, to: string | null, body, created_at, deleted}`, and `"chat_message"` added to the `AppNotification.kind` union.
  - `usePresence(pageId: string | null)` in `lib/presence.ts`: sends `POST /v1/pages/{id}/presence` on mount, every 20 seconds while the tab is visible, and when the tab becomes visible; sends `DELETE` when the tab is hidden and on unmount. No work while hidden.
  - `ringColor(userId: string): string` returning one of 6 fixed colours, stable per id. Each colour must have at least 4.5:1 contrast with white initials (verify with a small calculation and note the result in the commit message).
  - `PresenceRow({ pageId, meId })` showing people with `here` true (you first, with a ring), max 5 then a `+N` chip, name on hover and as `aria-label`, `SWR` key `["people", pageId]` with a 30 second refresh.
  - `page.tsx` calls `usePresence(id)`, renders `<PresenceRow />` between the title and the right-hand buttons, and its `useLive` handler refetches `["people", id]` on `presence.changed` and on `resync`.

- [ ] **Step 1: Implement** the types, hook, ring colours and row, and wire them into the header. Avatars are 28 px circles with initials.
- [ ] **Step 2: Verify** `npx tsc --noEmit` and `node scripts/check-contrast.mjs` pass.
- [ ] **Step 3: Browser check** with the stand-in harness in `/tmp/vp` (route interception): avatars appear for `here` people, you appear first, `+N` shows with 7 people, hidden tab stops heartbeats (count POST calls), reduced motion on.
- [ ] **Step 4: Commit** `Show who is on the page`.

### Task 5: Chat bubble, unread, and bell kind

**Files:**
- Create: `frontend/src/components/chat-bubble.tsx`, `frontend/src/lib/chat.ts`
- Modify: `frontend/src/app/(app)/pages/[id]/page.tsx`, `frontend/src/components/presence-row.tsx`, `frontend/src/components/notification-bell.tsx`

**Interfaces:**
- Consumes: Task 4 types and `["people", pageId]` data.
- Produces:
  - `useChat(pageId: string, meId: string)` in `lib/chat.ts` returning `{ open, setOpen, minimised, setMinimised, selected, select(id: string | null), unread: Record<string, number>, total: number, onEvent(e: LiveEvent | "resync") }`. `selected` null means Everyone. `onEvent` refetches `["messages", pageId, key]` for `message.*` events and increments `unread` for a message from someone else when the bubble is closed or another conversation is selected. Opening a conversation clears its count.
  - `ChatBubble({ chat, pageId, meId })`: a round launcher at the bottom right with an unread dot, opening a popover about 340 by 440 px (full width minus 16 px gutters under 480 px wide). Chips row (`Everyone` and teammates, with unread dots), message list (own messages right, others left, sender and time), composer with Send disabled when empty, Enter sends, Shift+Enter adds a line. Optimistic send that restores the text on failure and shows the server message. Own messages show Delete. Reads use `["messages", pageId, key]` with key `all` or the person id.
  - Clicking an avatar in `PresenceRow` (other than yours) calls `chat.select(id)` and `chat.setOpen(true)`.
  - `page.tsx` creates `const chat = useChat(id, meId)`, calls `chat.onEvent(e)` in the existing `useLive` handler, and renders the bubble in the viewer only.
  - The bell renders `chat_message` items with the body and a link to the page.
  - Accessibility: launcher and chips are buttons with labels, the popover is `role="dialog"` with `aria-label="Page chat"`, Escape minimises, new messages go to an `aria-live="polite"` region, and motion respects `useCalm()`.

- [ ] **Step 1: Implement** the hook, component and wiring.
- [ ] **Step 2: Verify** `npx tsc --noEmit` and `node scripts/check-contrast.mjs`.
- [ ] **Step 3: Browser check** with the harness: open and close, send to Everyone, switch to a private chip, unread dot appears for a message in another conversation and clears on open, failed send restores text, Escape minimises, a viewer can write, narrow viewport (390 px) fits, no layout shift of the page content, reduced motion. Take screenshots for the PR.
- [ ] **Step 4: Commit** `Add the page chat bubble`.

### Task 6: Documentation and final verification

**Files:**
- Modify: `backend/docs/SECURITY.md`, `backend/docs/SDD.md`, `README.md`

- [ ] **Step 1: Document** a new SECURITY section: chat and presence are people only, private messages are not readable by owners, events are not stored or sent to webhooks, access is rechecked on every event. Add the two tables and routes to the SDD. Add a short "Presence and chat" subsection with a screenshot to the README tour.
- [ ] **Step 2: Run everything:** full backend suite, ruff, tsc, contrast. Confirm green.
- [ ] **Step 3: Final review** of the whole branch diff against the spec; fix anything found.
- [ ] **Step 4: Commit** `Document presence and chat`, then produce one patch with `git format-patch` for delivery.
