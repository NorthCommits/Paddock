# Agent context: briefs, page notes and questions

Spec and plan in one file. Approved by the user in chat ("A, B, C implement it").

## Problem
A colleague's agent picks up a request with only the page and the comment. The person who asked
has the full discussion in their own Claude. The helper has to guess.

## Design
A. Brief. A request carries an optional `brief` (up to 4000 characters) written by the person or by
   their own Claude. Set when commenting with `@agent`, editable by the requester or page owner
   while the request is not done. Shown to everyone who can read the comment, so nothing hidden
   is shared. The full conversation is never sent, only the brief.
B. Page context note. `pages.context_note` (up to 8000 characters): decisions, constraints and
   terms. Editors and the owner set it. An agent can append a dated line when completing a
   request. Every request an agent lists carries the page note and the comment thread.
C. Needs info. New request status `needs_info`. A claiming agent calls `ask_requester`: its
   question is posted in the thread, the claim is released, the requester gets a bell item
   (`agent_question`). A person's reply in the thread, or an edit of the brief, puts the request
   back to open for the same approver. Claiming a `needs_info` request is refused.
D. Tool texts tell agents to read brief, note and thread first, and to state assumptions.

## Tasks
1. Backend: migration 0013, brief, context note, needs_info, MCP tools `set_request_brief`,
   `update_page_context`, `ask_requester`, `complete_request(context=...)`. Tests first.
2. Frontend: brief field in the composer, brief and needs-info shown in the thread, a page
   context sheet, bell kind.
3. Landing page, docs and review.
