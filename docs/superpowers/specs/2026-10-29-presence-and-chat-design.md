# Presence and the page chat bubble

Status: draft for review. Date: 2026-10-29.

## Goal

Show who is on a page right now, and let people talk to each other on the page without adding a
second column next to the comments. Comments stay the lasting record. The chat is for quick talk.

## What the person asked for

- Avatars of the members who are active, like a shared spreadsheet.
- A way to talk to members inside the page that is not a second stacked right column.
- Chosen: a floating chat bubble. It talks to everyone on the page, or privately to one person.
  Everyone with access to the page can use it, including viewers.

## Design

### Presence

- Avatars sit in the page header between the title and the Comments button. Each person has a
  stable colour shown as a ring. Hover shows the name. More than 5 people collapse into a "+N" chip.
- A person is here when their browser has the page open in a visible tab and has sent a heartbeat
  in the last 45 seconds. The client sends a heartbeat every 20 seconds, and a leave signal when the
  tab closes or hides.
- Only signed-in people appear. People on an anonymous share link are not shown.
- The viewer's own avatar is shown first with a ring, so the row is never empty.

### The bubble

- A round button at the bottom right of the page with an unread dot. It opens a compact popover
  (about 340 by 440 pixels). It can be minimised. The page never resizes.
- A row of chips at the top picks the conversation: `Everyone`, then one chip per teammate who has
  access. Clicking an avatar in the header opens the bubble on that person.
- Messages are plain text, up to 1000 characters, with the sender, time and a small avatar.
- A message may reference a comment by pasting its link. There is no second comment list.

### Rules

- Reading and writing `Everyone`: anyone who can open the page, including viewers.
- A private message is visible only to its sender and recipient. A page owner cannot read other
  people's private messages.
- The recipient of a private message must have access to the page.
- Removing someone from a page ends their access to the chat at once. Server checks use the same
  page access rule as every other page route.
- Messages are kept 30 days and then deleted. Deleting a page deletes its messages.
- Ruling: a private message creates a bell notification only if the recipient is not on the page
  at that moment. It never sends an email.
- A sender may delete their own message. Owners may delete any message in `Everyone`.
- Rate limit: 20 messages a minute per person.

### Data

- `page_presence(page_id, user_id, last_seen_at)`, primary key on page and user. Rows older than
  45 seconds are ignored and cleaned up lazily.
- `page_messages(id, page_id, sender_id, recipient_id null, body, created_at, deleted_at)`.
  `recipient_id` null means `Everyone`. Index on page and created time, and on recipient.

### API

- `POST /v1/pages/{id}/presence` heartbeat. `DELETE` for leave.
- `GET /v1/pages/{id}/presence` returns who is here (id, handle, display name, colour index).
- `GET /v1/pages/{id}/messages?with={user_id}&before=` returns `Everyone` when `with` is absent,
  otherwise the private thread with that person. Newest last, 50 per page.
- `POST /v1/pages/{id}/messages` with `body` and optional `to`.
- `DELETE /v1/messages/{id}`.
- New live events on the existing page stream: `presence.changed` and `message.created`. A private
  message event is sent only to the two people in it. Reconnects replay missed events.

### Frontend

- `PresenceRow` in the page header and `ChatBubble` over the page, both in the viewer only.
- SWR for the first load, and the existing live stream to update. Optimistic send, with the text
  restored if sending fails.
- Honour reduced motion. The bubble is keyboard reachable, has labelled controls, and announces
  new messages politely to screen readers.

## Not in this change

Typing indicators, read receipts, file sharing, browser push, agent messages in the chat,
and live cursors over page content.

## Testing

- Backend: presence appears and expires; private messages are visible only to the two people;
  viewers can read and write `Everyone`; removed members lose access; retention deletes old
  messages; rate limit; private event not delivered to others; bell only when absent.
- Browser: header avatars, bubble open and send, private chip, unread dot, reduced motion.

## Risks

- Heartbeats every 20 seconds per open tab add write load on the free database. One upsert per
  tab per 20 seconds is small, and the interval can be raised.
- The API on the free tier sleeps, so the first heartbeat after sleep can be slow. The row only
  needs to be eventually correct.
