"use client";

import { Bot, Check, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { CommentItem, Role, Thread, ThreadList } from "@/lib/api";
import { ago } from "@/lib/format";
import { cn } from "@/lib/utils";

type Filter = "open" | "resolved" | "all";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "open", label: "Open" },
  { id: "resolved", label: "Resolved" },
  { id: "all", label: "All" },
];

function statusChip(c: CommentItem) {
  const r = c.request;
  if (!r) return null;
  if (r.status === "open") return <Badge>Waiting for agent</Badge>;
  if (r.status === "claimed") return <Badge variant="success">Agent working</Badge>;
  if (r.status === "done") return <Badge variant="success">Done in v{r.result_version}</Badge>;
  return <Badge>Dismissed</Badge>;
}

// Highlights the word @agent inside a comment.
function Body({ text }: { text: string }) {
  const parts = text.split(/((?<![A-Za-z0-9_@])@agent(?![A-Za-z0-9_-]))/i);
  return (
    <p className="mt-1 whitespace-pre-wrap break-words text-[13px] text-foreground">
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className="rounded bg-primary-soft px-1 font-medium text-primary">{part}</span>
        ) : (
          part
        ),
      )}
    </p>
  );
}

export function CommentsPanel({
  pageId,
  role,
  me,
  version,
  onClose,
}: {
  pageId: string;
  role: Role;
  me: string | undefined;
  version: number | null;
  onClose: () => void;
}) {
  const [filter, setFilter] = useState<Filter>("open");
  const [error, setError] = useState("");
  const threads = useSWR(["comments", pageId, filter], () =>
    api<ThreadList>(`/v1/pages/${pageId}/comments${filter === "all" ? "" : `?status=${filter}`}`),
  );

  const { mutate } = useSWRConfig();
  const canComment = role !== "viewer";
  const canModerate = role === "owner" || role === "editor";

  async function run(work: () => Promise<unknown>) {
    try {
      setError("");
      await work();
      // Every filter shows the same threads, so refresh them all.
      await mutate((key) => Array.isArray(key) && key[0] === "comments" && key[1] === pageId);
    } catch (err) {
      setError((err as Error).message);
    }
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
              "rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors duration-[120ms]",
              filter === f.id ? "bg-primary-soft text-primary" : "text-muted-foreground hover:bg-muted",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <p role="alert" className="px-4 pt-3 text-[12px] text-destructive">{error}</p>}

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {threads.error ? (
          <p role="alert" className="text-[13px] text-destructive">{(threads.error as Error).message}</p>
        ) : !threads.data ? (
          [0, 1].map((n) => <Skeleton key={n} className="h-24" />)
        ) : threads.data.items.length === 0 ? (
          <p className="px-1 py-6 text-center text-[13px] text-muted-foreground">
            {filter === "resolved" ? "No resolved threads." : "No comments yet."}
          </p>
        ) : (
          threads.data.items.map((t) => (
            <ThreadCard
              key={t.id}
              thread={t}
              pageId={pageId}
              me={me}
              canComment={canComment}
              canModerate={canModerate}
              version={version}
              run={run}
            />
          ))
        )}
      </div>

      {canComment ? (
        <Composer
          hint="Mention @agent to ask your agent to revise this page"
          label="Comment"
          onSend={(body) => run(() => api(`/v1/pages/${pageId}/comments`, { method: "POST", body: { body, version } }))}
        />
      ) : (
        <p className="border-t border-border px-4 py-3 text-[12px] text-muted-foreground">You can read comments but not write them.</p>
      )}
    </div>
  );
}

function ThreadCard({
  thread,
  pageId,
  me,
  canComment,
  canModerate,
  version,
  run,
}: {
  thread: Thread;
  pageId: string;
  me: string | undefined;
  canComment: boolean;
  canModerate: boolean;
  version: number | null;
  run: (work: () => Promise<unknown>) => Promise<void>;
}) {
  const [replying, setReplying] = useState(false);
  const resolved = !!thread.resolved_at;
  const live = thread.request && (thread.request.status === "open" || thread.request.status === "claimed");
  const all = [thread, ...thread.replies];

  return (
    <article className={cn("rounded-lg border border-border bg-card p-3", resolved && "opacity-70")}>
      {all.map((c) => (
        <Message key={c.id} c={c} me={me} canModerate={canModerate} run={run} first={c.id === thread.id} />
      ))}

      <div className="mt-2 flex flex-wrap items-center gap-1">
        {canComment && !resolved && (
          <Button size="sm" variant="ghost" onClick={() => setReplying((v) => !v)}>Reply</Button>
        )}
        {canComment && !thread.deleted && (
          <Button size="sm" variant="ghost" onClick={() => run(() => api(`/v1/comments/${thread.id}/resolve`, { method: "POST", body: { resolved: !resolved } }))}>
            {resolved ? <RotateCcw aria-hidden="true" /> : <Check aria-hidden="true" />}
            {resolved ? "Reopen" : "Resolve"}
          </Button>
        )}
        {canModerate && live && (
          <Button size="sm" variant="ghost" onClick={() => run(() => api(`/v1/requests/${thread.request!.id}/dismiss`, { method: "POST", body: {} }))}>
            Dismiss request
          </Button>
        )}
      </div>
      {resolved && thread.resolved_by && <p className="mt-1 text-[12px] text-subtle">Resolved by @{thread.resolved_by}</p>}

      {replying && (
        <div className="mt-2">
          <Composer
            compact
            label="Reply"
            hint="Mention @agent to ask for another change"
            onSend={async (body) => {
              await run(() => api(`/v1/pages/${pageId}/comments`, { method: "POST", body: { body, parent_id: thread.id, version } }));
              setReplying(false);
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
    <div className={cn(!first && "mt-3 border-t border-border pt-3")}>
      <div className="flex flex-wrap items-center gap-1.5 text-[12px] text-muted-foreground">
        {c.deleted ? (
          <span>Deleted</span>
        ) : (
          <>
            {c.author.by_agent && <Bot size={12} aria-hidden="true" />}
            <span className="font-medium text-foreground">@{c.author.handle}</span>
            {c.author.by_agent && <span>(agent)</span>}
          </>
        )}
        <span className="tnum">{ago(c.created_at)}</span>
        {c.version_number && <span className="tnum">on v{c.version_number}</span>}
        {c.edited_at && <span>edited</span>}
        <span className="flex-1" />
        {statusChip(c)}
      </div>

      {c.deleted ? (
        <p className="mt-1 text-[13px] italic text-subtle">This comment was deleted.</p>
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

      {c.request?.status === "dismissed" && c.request.dismiss_reason && (
        <p className="mt-1 text-[12px] text-subtle">Dismissed: {c.request.dismiss_reason}</p>
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

function Composer({
  label,
  hint,
  initial = "",
  compact,
  onSend,
  onCancel,
}: {
  label: string;
  hint: string;
  initial?: string;
  compact?: boolean;
  onSend: (body: string) => void | Promise<void>;
  onCancel?: () => void;
}) {
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);
  const empty = text.trim().length === 0;

  async function send() {
    if (empty || busy) return;
    setBusy(true);
    try {
      await onSend(text.trim());
      setText("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={cn(!compact && "border-t border-border p-3")}>
      <textarea
        aria-label={label}
        value={text}
        maxLength={5000}
        rows={compact ? 2 : 3}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            void send();
          }
        }}
        className="mt-1 w-full resize-none rounded-md border border-input-border bg-card px-2.5 py-2 text-[13px] text-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25"
      />
      <div className="mt-1.5 flex items-center gap-2">
        {hint && <p className="flex-1 text-[11px] text-subtle">{hint}</p>}
        {!hint && <span className="flex-1" />}
        {onCancel && <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>}
        <Button size="sm" onClick={send} disabled={empty || busy}>{label === "Comment" ? "Send" : label === "Reply" ? "Reply" : "Save"}</Button>
      </div>
    </div>
  );
}
