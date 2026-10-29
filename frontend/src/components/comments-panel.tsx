"use client";

import { Ban, Bot, Check, Crosshair, RotateCcw, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { Anchor, CommentItem, Me, Role, Thread, ThreadList } from "@/lib/api";
import { ago } from "@/lib/format";
import { useCalm } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Filter = "open" | "resolved" | "rejected" | "all";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "open", label: "Open" },
  { id: "resolved", label: "Resolved" },
  { id: "rejected", label: "Rejected" },
  { id: "all", label: "All" },
];

// Every thread is fetched once. The tabs are views of that one list, so switching is instant and a
// change (resolve, reject, send) lands in the right tab straight away.
export function useThreads(pageId: string) {
  return useSWR(["comments", pageId], () => api<ThreadList>(`/v1/pages/${pageId}/comments`));
}

/** Which tab a thread belongs to: resolved wins, then a rejected request, otherwise open. */
export function bucket(t: Thread): "open" | "resolved" | "rejected" {
  if (t.resolved_at) return "resolved";
  if (t.request?.status === "dismissed") return "rejected";
  return "open";
}

/** Number each open thread that points at a spot on the page, in order. The page shows the same numbers. */
export function markNumbers(threads: Thread[] | undefined): Map<string, number> {
  const out = new Map<string, number>();
  (threads ?? []).filter((t) => t.anchor && !t.deleted && bucket(t) === "open").forEach((t, i) => out.set(t.id, i + 1));
  return out;
}

const AGENT = /((?<![A-Za-z0-9_@])@agent(?![A-Za-z0-9_-]))/i;

function statusChip(c: CommentItem) {
  const r = c.request;
  if (!r) return null;
  if (r.status === "open") return <Badge>Waiting for agent</Badge>;
  if (r.status === "claimed") return <Badge variant="success">Agent working</Badge>;
  if (r.status === "done") return <Badge variant="success">Done in v{r.result_version}</Badge>;
  return <Badge>Rejected</Badge>;
}

// Shows a comment, with @agent standing out as a chip.
function Body({ text }: { text: string }) {
  const parts = text.split(AGENT);
  return (
    <p className="mt-1.5 whitespace-pre-wrap break-words text-[14px] leading-[1.5] text-foreground">
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className="rounded-md bg-primary-soft px-1.5 py-0.5 font-semibold text-primary ring-1 ring-primary/30">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </p>
  );
}

function quoteOf(a: Anchor): string {
  return a.selected || a.quote || (a.tag === "img" ? "Image" : "This part");
}

// What a comment points at. Pressing it scrolls the page to that spot.
function AnchorChip({ anchor, n, onShow }: { anchor: Anchor; n?: number; onShow?: () => void }) {
  const text = quoteOf(anchor);
  return (
    <button
      type="button"
      onClick={onShow}
      disabled={!onShow}
      title={onShow ? "Show this on the page" : undefined}
      className="mt-1.5 flex w-full items-start gap-2 rounded-md border border-border bg-muted px-2.5 py-1.5 text-left text-[13px] text-foreground transition-colors duration-[120ms] enabled:hover:border-primary/50"
    >
      {n ? (
        <span className="mt-px flex min-w-5 items-center justify-center rounded-full bg-signal px-1.5 text-[11px] font-semibold text-signal-foreground">{n}</span>
      ) : (
        <Crosshair size={14} aria-hidden="true" className="mt-0.5 shrink-0 text-muted-foreground" />
      )}
      <span className="min-w-0">
        {anchor.section && anchor.section !== text && <span className="block truncate text-[12px] text-muted-foreground">In {anchor.section}</span>}
        <span className="line-clamp-2 break-words">&ldquo;{text}&rdquo;</span>
      </span>
    </button>
  );
}

export function CommentsPanel({
  pageId,
  role,
  me,
  version,
  draft,
  onDraft,
  activeId,
  onShow,
  onClose,
}: {
  pageId: string;
  role: Role;
  me: string | undefined;
  version: number | null;
  draft: Anchor | null;
  onDraft: (anchor: Anchor | null) => void;
  activeId: string | null;
  onShow: (anchor: Anchor) => void;
  onClose: () => void;
}) {
  const [filter, setFilter] = useState<Filter>("open");
  const [error, setError] = useState("");
  const threads = useThreads(pageId);
  const all = threads.data?.items;
  const numbers = markNumbers(all);
  const self = useSWR<Me>("me", null);
  const calm = useCalm();
  const listRef = useRef<HTMLDivElement>(null);

  const { mutate } = useSWRConfig();
  const canComment = role !== "viewer";
  const canModerate = role === "owner" || role === "editor";

  const shown = (all ?? []).filter((t) => filter === "all" || bucket(t) === filter);
  const counts = { open: 0, resolved: 0, rejected: 0 };
  (all ?? []).forEach((t) => (counts[bucket(t)] += 1));

  const refresh = () => mutate(["comments", pageId]);
  // Change the list on screen first. The server is told afterwards and the real list is fetched.
  const change = (fn: (items: Thread[]) => Thread[]) =>
    mutate(["comments", pageId], (cur?: ThreadList) => (cur ? { items: fn(cur.items) } : cur), { revalidate: false });
  const edit = (id: string, fn: (t: Thread) => Thread) => change((items) => items.map((t) => (t.id === id ? fn(t) : t)));

  async function run(work: () => Promise<unknown>) {
    try {
      setError("");
      await work();
    } catch (err) {
      setError((err as Error).message);
    }
    await refresh();
  }

  async function setResolved(t: Thread, resolved: boolean) {
    const by = self.data?.user.handle ?? "";
    await edit(t.id, (x) => ({ ...x, resolved_at: resolved ? new Date().toISOString() : null, resolved_by: resolved ? by : null }));
    await run(() => api(`/v1/comments/${t.id}/resolve`, { method: "POST", body: { resolved } }));
  }

  async function reject(t: Thread, reason: string) {
    if (!t.request) return;
    const id = t.request.id;
    await edit(t.id, (x) => ({ ...x, request: x.request && { ...x.request, status: "dismissed", dismiss_reason: reason || null } }));
    await run(() => api(`/v1/requests/${id}/dismiss`, { method: "POST", body: reason ? { reason } : {} }));
  }

  // A new comment or reply shows at once, marked as sent when the server answers. If it fails the
  // text stays in the box so nothing is lost.
  async function post(body: string, extra: { parent?: string; anchor?: Anchor | null } = {}) {
    const me = self.data?.user;
    const asks = /(^|[^A-Za-z0-9_@])@agent(?![A-Za-z0-9_-])/i.test(body);
    const item: Thread = {
      id: `sending-${Date.now()}`,
      page_id: pageId,
      parent_id: extra.parent ?? null,
      version_number: version,
      author: { user_id: me?.id ?? null, handle: me?.handle ?? null, display_name: me?.display_name ?? null, by_agent: false },
      body,
      mentions_agent: asks,
      created_at: new Date().toISOString(),
      edited_at: null,
      deleted: false,
      resolved_at: null,
      resolved_by: null,
      anchor: extra.anchor ?? null,
      request: asks && !extra.parent ? { id: "sending", status: "open", base_version: null, result_version: null, claim_expires_at: null, dismiss_reason: null } : null,
      replies: [],
    };
    await change((items) =>
      extra.parent ? items.map((t) => (t.id === extra.parent ? { ...t, replies: [...t.replies, item] } : t)) : [...items, item],
    );
    if (!extra.parent) {
      if (filter === "resolved" || filter === "rejected") setFilter("open");
      requestAnimationFrame(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: calm ? "auto" : "smooth" }));
    }
    try {
      setError("");
      await api(`/v1/pages/${pageId}/comments`, {
        method: "POST",
        body: { body, version, ...(extra.parent ? { parent_id: extra.parent } : {}), ...(extra.anchor ? { anchor: extra.anchor } : {}) },
      });
    } catch (err) {
      setError((err as Error).message);
      await refresh();
      throw err;
    }
    await refresh();
  }

  return (
    <div className="flex h-full w-96 max-w-[100vw] flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-[15px] font-semibold text-foreground">Comments</h2>
        <button aria-label="Close comments" onClick={onClose} className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted">
          <X size={16} />
        </button>
      </div>

      <div className="flex gap-1 border-b border-border px-3 py-2" role="tablist" aria-label="Filter comments">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            role="tab"
            aria-selected={filter === f.id}
            onClick={() => setFilter(f.id)}
            className={cn(
              "rounded-md px-2.5 py-1 text-[13px] font-medium transition-colors duration-[120ms]",
              filter === f.id ? "bg-primary-soft text-primary" : "text-muted-foreground hover:bg-muted",
            )}
          >
            {f.label}
            {f.id !== "all" && all && counts[f.id] > 0 && <span className="tnum ml-1 opacity-80">{counts[f.id]}</span>}
          </button>
        ))}
      </div>

      {error && <p role="alert" className="px-4 pt-3 text-[13px] text-destructive">{error}</p>}

      <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {threads.error ? (
          <p role="alert" className="text-[14px] text-destructive">{(threads.error as Error).message}</p>
        ) : !threads.data ? (
          [0, 1].map((n) => <Skeleton key={n} className="h-24" />)
        ) : shown.length === 0 ? (
          <p className="px-1 py-6 text-center text-[14px] text-muted-foreground">
            {filter === "resolved"
              ? "No resolved threads."
              : filter === "rejected"
                ? "Nothing rejected. Requests you turn down, with your reason, are kept here."
                : "No comments yet. Hover any part of the page and press + to comment on it."}
          </p>
        ) : (
          <AnimatePresence initial={false}>
            {shown.map((t) => (
              <motion.div
                key={t.id}
                layout={calm ? false : "position"}
                initial={calm ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={calm ? { opacity: 0 } : { opacity: 0, height: 0, marginTop: 0, scale: 0.98 }}
                transition={{ duration: calm ? 0 : 0.22, ease: [0.32, 0.72, 0, 1] }}
              >
                <ThreadCard
                  thread={t}
                  me={me}
                  canComment={canComment}
                  canModerate={canModerate}
                  number={numbers.get(t.id)}
                  active={activeId === t.id}
                  run={run}
                  post={post}
                  onResolve={(resolved) => void setResolved(t, resolved)}
                  onReject={(reason) => void reject(t, reason)}
                  onShow={onShow}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {canComment ? (
        <Composer
          hint="Mention @agent to ask your agent to revise this page"
          label="Comment"
          anchor={draft}
          onClearAnchor={() => onDraft(null)}
          onSend={async (body) => {
            const attached = draft;
            onDraft(null);
            try {
              await post(body, { anchor: attached });
            } catch (err) {
              onDraft(attached);
              throw err;
            }
          }}
        />
      ) : (
        <p className="border-t border-border px-4 py-3 text-[13px] text-muted-foreground">You can read comments but not write them.</p>
      )}
    </div>
  );
}

function ThreadCard({
  thread,
  me,
  canComment,
  canModerate,
  number,
  active,
  run,
  post,
  onResolve,
  onReject,
  onShow,
}: {
  thread: Thread;
  me: string | undefined;
  canComment: boolean;
  canModerate: boolean;
  number: number | undefined;
  active: boolean;
  run: (work: () => Promise<unknown>) => Promise<void>;
  post: (body: string, extra?: { parent?: string }) => Promise<void>;
  onResolve: (resolved: boolean) => void;
  onReject: (reason: string) => void;
  onShow: (anchor: Anchor) => void;
}) {
  const [replying, setReplying] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const ref = useRef<HTMLElement>(null);
  const resolved = !!thread.resolved_at;
  const rejected = !resolved && thread.request?.status === "dismissed";
  const live = thread.request && thread.request.id !== "sending" && (thread.request.status === "open" || thread.request.status === "claimed");
  const all = [thread, ...thread.replies];

  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [active]);

  return (
    <article
      ref={ref}
      className={cn(
        "rounded-lg border bg-card p-3 transition-colors duration-300",
        active ? "border-primary ring-2 ring-primary/30" : "border-border",
        (resolved || rejected) && "bg-muted",
      )}
    >
      {thread.anchor && !thread.deleted && (
        <AnchorChip anchor={thread.anchor} n={resolved || rejected ? undefined : number} onShow={() => onShow(thread.anchor!)} />
      )}
      {all.map((c) => (
        <Message key={c.id} c={c} me={me} canModerate={canModerate} run={run} first={c.id === thread.id} />
      ))}

      <div className="mt-2 flex flex-wrap items-center gap-1">
        {canComment && !resolved && (
          <Button size="sm" variant="ghost" onClick={() => setReplying((v) => !v)}>Reply</Button>
        )}
        {canComment && !thread.deleted && (
          <Button size="sm" variant="ghost" onClick={() => onResolve(!resolved)}>
            {resolved ? <RotateCcw aria-hidden="true" /> : <Check aria-hidden="true" />}
            {resolved ? "Reopen" : "Resolve"}
          </Button>
        )}
        {canModerate && live && !rejecting && (
          <Button size="sm" variant="ghost" onClick={() => setRejecting(true)}>
            <Ban aria-hidden="true" /> Reject
          </Button>
        )}
      </div>
      {resolved && thread.resolved_by && <p className="mt-1 text-[13px] text-muted-foreground">Resolved by @{thread.resolved_by}</p>}
      {rejected && thread.request?.dismiss_reason && (
        <p className="mt-1 text-[13px] text-muted-foreground">Rejected: {thread.request.dismiss_reason}</p>
      )}

      {rejecting && (
        <form
          className="mt-2 space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            onReject(reason.trim());
            setRejecting(false);
            setReason("");
          }}
        >
          <input
            autoFocus
            aria-label="Reason for rejecting (optional)"
            placeholder="Why? (optional, your agent and the author will see it)"
            value={reason}
            maxLength={500}
            onChange={(e) => setReason(e.target.value)}
            className="w-full rounded-md border border-input-border bg-card px-2.5 py-1.5 text-[14px] text-foreground placeholder:text-muted-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25"
          />
          <div className="flex justify-end gap-1">
            <Button type="button" size="sm" variant="ghost" onClick={() => setRejecting(false)}>Cancel</Button>
            <Button type="submit" size="sm">Reject request</Button>
          </div>
        </form>
      )}

      {replying && (
        <div className="mt-2">
          <Composer
            compact
            label="Reply"
            hint="Mention @agent to ask for another change"
            onSend={async (body) => {
              setReplying(false);
              await post(body, { parent: thread.id });
            }}
          />
        </div>
      )}
    </article>
  );
}

function Message({
  c,
  me,
  canModerate,
  run,
  first,
}: {
  c: CommentItem;
  me: string | undefined;
  canModerate: boolean;
  run: (work: () => Promise<unknown>) => Promise<void>;
  first: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const mine = !!me && c.author.user_id === me && !c.author.by_agent;
  const canDelete = !c.deleted && (mine || canModerate);

  return (
    <div className={cn(!first && "mt-3 border-t border-border pt-3", first && "mt-2")}>
      <div className="flex flex-wrap items-center gap-1.5 text-[13px] text-muted-foreground">
        {c.deleted ? (
          <span>Deleted</span>
        ) : (
          <>
            {c.author.by_agent && <Bot size={13} aria-hidden="true" />}
            {c.author.by_agent ? (
              <span className="font-semibold text-foreground">{c.author.agent_label ?? `@${c.author.handle}'s agent`}</span>
            ) : (
              <span className="font-semibold text-foreground">@{c.author.handle}</span>
            )}
          </>
        )}
        <span className="tnum">{ago(c.created_at)}</span>
        {c.version_number && <span className="tnum">on v{c.version_number}</span>}
        {c.edited_at && <span>edited</span>}
        <span className="flex-1" />
        {statusChip(c)}
      </div>

      {c.deleted ? (
        <p className="mt-1 text-[14px] italic text-muted-foreground">This comment was deleted.</p>
      ) : editing ? (
        <Composer
          compact
          label="Save"
          initial={c.body}
          hint=""
          onSend={async (body) => {
            await run(() => api(`/v1/comments/${c.id}`, { method: "PATCH", body: { body } }));
            setEditing(false);
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <Body text={c.body} />
      )}

      {!c.deleted && !editing && (mine || canDelete) && (
        <div className="mt-1 flex gap-1">
          {mine && <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Edit</Button>}
          {canDelete && (
            <Button size="sm" variant="ghost" onClick={() => run(() => api(`/v1/comments/${c.id}`, { method: "DELETE" }))}>
              Delete
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

// Both layers use these, so the highlight lines up with the letters exactly.
const FIELD = "px-2.5 py-2 text-[14px] leading-[1.5] whitespace-pre-wrap break-words";

function Composer({
  label,
  hint,
  initial = "",
  compact,
  anchor,
  onClearAnchor,
  onSend,
  onCancel,
}: {
  label: string;
  hint: string;
  initial?: string;
  compact?: boolean;
  anchor?: Anchor | null;
  onClearAnchor?: () => void;
  onSend: (body: string) => void | Promise<void>;
  onCancel?: () => void;
}) {
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);
  const field = useRef<HTMLTextAreaElement>(null);
  const mirror = useRef<HTMLDivElement>(null);
  const empty = text.trim().length === 0;

  // A new spot picked on the page puts the cursor here, ready to type.
  useEffect(() => {
    if (anchor) field.current?.focus();
  }, [anchor]);

  async function send() {
    if (empty || busy) return;
    const body = text.trim();
    // The box empties at once. If sending fails the words come back, so nothing is lost.
    setText("");
    setBusy(true);
    try {
      await onSend(body);
    } catch {
      setText((now) => (now ? now : body));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={cn(!compact && "border-t border-border p-3")}>
      {anchor && (
        <div className="relative">
          <AnchorChip anchor={anchor} />
          <button
            type="button"
            aria-label="Remove the attached part of the page"
            onClick={onClearAnchor}
            className="absolute right-1.5 top-3 flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-card hover:text-foreground"
          >
            <X size={14} />
          </button>
        </div>
      )}
      <div className="relative mt-1.5 rounded-md bg-card">
        <div
          ref={mirror}
          aria-hidden="true"
          className={cn(FIELD, "pointer-events-none absolute inset-0 overflow-hidden rounded-md border border-transparent text-transparent")}
        >
          {text.split(AGENT).map((part, i) =>
            i % 2 === 1 ? (
              <mark key={i} className="rounded-sm bg-primary-soft text-transparent shadow-[0_0_0_2px_var(--primary-soft),0_0_0_3px_color-mix(in_srgb,var(--primary)_35%,transparent)]">
                {part}
              </mark>
            ) : (
              part
            ),
          )}
          {"​"}
        </div>
        <textarea
          ref={field}
          aria-label={label}
          value={text}
          maxLength={5000}
          rows={compact ? 2 : 3}
          placeholder={anchor ? "What should change here?" : undefined}
          onChange={(e) => setText(e.target.value)}
          onScroll={(e) => {
            if (mirror.current) mirror.current.scrollTop = e.currentTarget.scrollTop;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void send();
            }
          }}
          className={cn(
            FIELD,
            "relative block w-full resize-none rounded-md border border-input-border bg-transparent text-foreground placeholder:text-muted-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25",
          )}
        />
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        {hint && <p className="flex-1 text-[12px] text-muted-foreground">{hint}</p>}
        {!hint && <span className="flex-1" />}
        {onCancel && <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>}
        <Button size="sm" onClick={send} disabled={empty || busy}>{label === "Comment" ? "Send" : label === "Reply" ? "Reply" : "Save"}</Button>
      </div>
    </div>
  );
}
