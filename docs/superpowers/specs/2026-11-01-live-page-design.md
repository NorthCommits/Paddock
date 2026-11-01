# A calmer, livelier page

Status: built, waiting for review. Date: 2026-11-01.

## Goal

Make reading and discussing a page feel alive and smooth, on a phone as well as on a computer,
using what we learned from how Spacesheep handles pages. Paddock keeps its own look.

## What was built

1. **Stable block ids.** The page helper script names each part of a page. A part with
   `data-pd-id` keeps that name for ever; any other part is named from its tag and first words.
   Comments store the name and look for it first, then fall back to the older quote and path
   search. The `publish_page` tool text tells agents to keep `data-pd-id` attributes.
2. **Pin mode.** A "Pin a comment" button turns commenting on. A tap or click on a part starts a
   comment on it (this is the way to comment on a phone). Escape turns it off. Hovering or focusing
   a numbered marker shows a small preview card: author, first lines, replies, resolved or not.
3. **Agent activity.** While a request on the page is claimed, the header shows "Agent is working"
   and its lower edge glows. When the tab is hidden, the tab title gets a count of new comments,
   requests and versions, and clears when the tab is shown.
4. **Polish.** A floating rounded header, one set of motion values (150, 180, 400 ms), a fade when a
   page opens, icon-only buttons on small screens, 44 px touch targets on touch devices, and
   reduced motion respected.
5. **Who is where.** The helper script reports the block a person hovers or selects (at most four
   times a second, only while someone else is on the page and the person allows it). Others see a
   dashed outline (looking) or a solid one (selecting) in that person's colour with a name tag.
   Places are live only and disappear after 8 seconds without movement. Each person can hide theirs
   with an eye button; the choice is kept in the browser and defaults to on.
6. **Reactions and install.** Four reactions (like, love, cheer, eyes) drawn as small line icons,
   shown as chips on a part and updated live. They need the comment role. Paddock also ships a web
   manifest, a maskable icon and safe-area handling, so it can be installed from the browser.
   Push notifications are not included.

## Decisions

- Computed ids change when a part's words change, so then the older search is used. Explicit
  `data-pd-id` ids do not have this problem, which is why agents are told to add them.
- Reactions and places only line up for people viewing the same version of the page.
- No emoji are used anywhere; reactions are icons.
- Places are never stored and never sent to agents or webhooks.

## Not done

Server-side stamping of ids at publish time, push notifications and a native app shell.

## Migration

Run migration `0014_block_reactions` on deploy (it follows 0012 and 0013).
