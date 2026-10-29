"use client";

import { ArrowLeft, Bot, ExternalLink, History, MessageSquare, LogOut, Pencil, RotateCcw, Share2, Trash2, Upload, User, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { AddAgentHint } from "@/components/add-agent-hint";
import { CommentsPanel, markNumbers, useThreads } from "@/components/comments-panel";
import { PageFrame } from "@/components/page-frame";
import { PresenceRow } from "@/components/presence-row";
import { ShareSheet } from "@/components/share-sheet";
import { UploadSheet } from "@/components/upload-sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, ROLE_LABEL, api, fetchMe } from "@/lib/api";
import type { Anchor, Page, Publish, Version, VersionList, ViewUrl } from "@/lib/api";
import { ago, bytes } from "@/lib/format";
import { useLive } from "@/lib/live";
import { usePresence } from "@/lib/presence";
import { cn } from "@/lib/utils";

const TWELVE_MINUTES = 12 * 60 * 1000; // view links last 15 minutes

export default function PageViewer() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const page = useSWR(["page", id], () => api<Page>(`/v1/pages/${id}`), { shouldRetryOnError: false });
  const versions = useSWR(["versions", id], () => api<VersionList>(`/v1/pages/${id}/versions?limit=100`));

  const [picked, setPicked] = useState<number | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const me = useSWR("me", fetchMe);
  usePresence(id);
  const [deleting, setDeleting] = useState(false);
  const [rollback, setRollback] = useState<Version | null>(null);
  const [notice, setNotice] = useState("");
  const [failed, setFailed] = useState("");

  const current = page.data?.current_version?.number ?? null;
  const shown = picked ?? current;

  // Asked for straight away, in parallel with the page itself. No version means the latest one.
  const view = useSWR(
    ["view", id, picked ?? "latest"],
    () => api<ViewUrl>(`/v1/pages/${id}/view-url`, { method: "POST", body: { version: picked } }),
    { refreshInterval: TWELVE_MINUTES, revalidateOnFocus: false, shouldRetryOnError: false, keepPreviousData: true },
  );

  // Comments that point at a spot on the page: numbered markers on the page, and the attached spot in the composer.
  const [draft, setDraft] = useState<Anchor | null>(null);
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ anchor: Anchor; key: number } | null>(null);
  const threads = useThreads(id);
  const marks = useMemo(() => {
    const numbers = markNumbers(threads.data?.items);
    return (threads.data?.items ?? []).flatMap((t) => (t.anchor && numbers.has(t.id) ? [{ id: t.id, n: numbers.get(t.id)!, anchor: t.anchor }] : []));
  }, [threads.data]);

  // Changes made by other people or by an agent arrive here at once, so the screen stays current.
  const { mutate: refetch } = useSWRConfig();
  useLive(`/v1/pages/${id}/events`, (e) => {
    const comments = () => refetch((k) => Array.isArray(k) && k[0] === "comments" && k[1] === id);
    const people = () => refetch((k) => Array.isArray(k) && k[0] === "people" && k[1] === id);
    if (e === "resync") {
      void Promise.all([comments(), people(), page.mutate(), versions.mutate()]);
      return;
    }
    if (e.type === "presence.changed") void people();
    if (e.type.startsWith("comment.") || e.type.startsWith("request.")) void comments();
    if (e.type === "version.published" || e.type === "version.rolled_back") {
      void Promise.all([page.mutate(), versions.mutate(), picked === null ? view.mutate() : undefined]);
      setNotice(`Version ${String(e.data.version)} is live.`);
    }
    if (e.type === "page.updated" || e.type === "page.deleted") void page.mutate();
  });

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(t);
  }, [notice]);

  async function refresh() {
    await Promise.all([page.mutate(), versions.mutate(), view.mutate()]);
  }

  async function doRollback() {
    if (!rollback) return;
    try {
      const r = await api<Publish>(`/v1/pages/${id}/versions/${rollback.number}/rollback`, { method: "POST" });
      setRollback(null);
      setPicked(null);
      await refresh();
      setNotice(r.created ? `Restored version ${rollback.number} as version ${r.version.number}.` : "That version is already live.");
    } catch (err) {
      setFailed((err as Error).message);
    }
  }

  async function doLeave() {
    if (!me.data) return;
    try {
      await api(`/v1/pages/${id}/members/${me.data.user.id}`, { method: "DELETE" });
      router.push("/pages");
    } catch (err) {
      setFailed((err as Error).message);
    }
  }

  async function doDelete() {
    try {
      await api(`/v1/pages/${id}`, { method: "DELETE" });
      router.push("/pages");
    } catch (err) {
      setFailed((err as Error).message);
    }
  }

  if (page.error) {
    const missing = page.error instanceof ApiError && page.error.status === 404;
    return (
      <div className="rounded-xl border border-border bg-card p-8 shadow-card">
        <h1 className="text-[17px] font-semibold text-foreground">{missing ? "Page not found" : "Could not load this page"}</h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {missing ? "It may have been deleted, or it belongs to someone else." : (page.error as Error).message}
        </p>
        <Link href="/pages" className="mt-4 inline-flex items-center gap-1.5 text-[13px] text-primary hover:underline">
          <ArrowLeft size={14} /> Back to pages
        </Link>
      </div>
    );
  }

  const p = page.data;
  const old = !!p && shown !== null && shown !== current;
  const isOwner = p?.role === "owner";
  const canEdit = p?.role === "owner" || p?.role === "editor";
  const shownVersion = versions.data?.items.find((v) => v.number === shown);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-background px-4 py-2.5">
        <Link href="/pages" aria-label="Back to pages" className="flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted">
          <ArrowLeft size={16} />
        </Link>
        {p ? <Title page={p} canRename={isOwner} onSaved={async () => { await refresh(); setNotice("Saved."); }} /> : <Skeleton className="h-6 w-48" />}
        {p && <Badge variant={old ? "neutral" : "success"}>{old ? `Viewing v${shown}` : `v${current}`}</Badge>}
        {p && !isOwner && <Badge>{ROLE_LABEL[p.role]}</Badge>}
        <span className="flex-1" />
        {p && <PresenceRow pageId={id} meId={me.data?.user.id} />}
        <AddAgentHint />
        {old && canEdit && (
          <Button size="sm" variant="secondary" onClick={() => shownVersion && setRollback(shownVersion)}>
            <RotateCcw aria-hidden="true" /> Restore this version
          </Button>
        )}
        {old && (
          <Button size="sm" variant="ghost" onClick={() => setPicked(null)}>Back to latest</Button>
        )}
        {canEdit && (
          <Button size="sm" variant="secondary" onClick={() => setUploading(true)}>
            <Upload aria-hidden="true" /> New version
          </Button>
        )}
        {isOwner && (
          <Button size="sm" variant="secondary" onClick={() => setSharing(true)}>
            <Share2 aria-hidden="true" /> Share
          </Button>
        )}
        <Button size="sm" variant={showComments ? "default" : "secondary"} onClick={() => setShowComments((v) => !v)} aria-pressed={showComments}>
          <MessageSquare aria-hidden="true" /> Comments
        </Button>
        <Button size="sm" variant={showHistory ? "default" : "secondary"} onClick={() => setShowHistory((v) => !v)} aria-pressed={showHistory}>
          <History aria-hidden="true" /> History
        </Button>
        {view.data && (
          <a
            href={view.data.url}
            target="_blank"
            rel="noreferrer"
            aria-label="Open in a new tab"
            className="flex size-8 items-center justify-center rounded-md border border-border bg-card text-muted-foreground hover:text-foreground"
          >
            <ExternalLink size={16} />
          </a>
        )}
        {isOwner && (
          <button
            aria-label="Delete page"
            onClick={() => setDeleting(true)}
            className="flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-destructive"
          >
            <Trash2 size={16} />
          </button>
        )}
        {p && !isOwner && (
          <Button size="sm" variant="ghost" onClick={() => setLeaving(true)}>
            <LogOut aria-hidden="true" /> Leave
          </Button>
        )}
      </div>

      <div className="relative flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1 bg-muted">
          {view.error ? (
            <p role="alert" className="p-6 text-[13px] text-destructive">{(view.error as Error).message}</p>
          ) : (
            <PageFrame
              url={view.data?.url}
              version={view.data?.version}
              title={p ? `${p.title}, version ${shown}` : "Page"}
              marks={marks}
              focus={focus}
              onComment={(anchor) => {
                setDraft(anchor);
                setShowComments(true);
              }}
              onMark={(threadId) => {
                setActiveThread(threadId);
                setShowComments(true);
              }}
              onMissing={() => setNotice("That part is not in this version.")}
            />
          )}
          <AnimatePresence>
            {notice && (
              <motion.p
                role="status"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-foreground px-4 py-2 text-[13px] text-background shadow-float"
              >
                {notice}
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        <AnimatePresence initial={false}>
          {showComments && p && (
            <motion.aside
              key="comments"
              aria-label="Comments"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 384, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.32, ease: [0.32, 0.72, 0, 1] }}
              className="absolute inset-y-0 right-0 z-10 overflow-hidden border-l border-border bg-background md:static"
            >
              <CommentsPanel
                pageId={id}
                role={p.role}
                me={me.data?.user.id}
                version={shown}
                draft={draft}
                onDraft={setDraft}
                activeId={activeThread}
                onShow={(anchor) => setFocus({ anchor, key: Date.now() })}
                onClose={() => setShowComments(false)}
              />
            </motion.aside>
          )}
          {showHistory && (
            <motion.aside
              key="history"
              aria-label="Version history"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 320, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.32, ease: [0.32, 0.72, 0, 1] }}
              className="absolute inset-y-0 right-0 z-10 overflow-hidden border-l border-border bg-background md:static"
            >
              <div className="flex h-full w-80 max-w-[100vw] flex-col">
                <div className="flex items-center justify-between border-b border-border px-4 py-3">
                  <h2 className="text-[15px] font-semibold text-foreground">History</h2>
                  <button aria-label="Close history" onClick={() => setShowHistory(false)} className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted">
                    <X size={16} />
                  </button>
                </div>
                <ul className="flex-1 overflow-y-auto p-2">
                  {!versions.data
                    ? [0, 1, 2].map((n) => <Skeleton key={n} className="m-1 h-16" />)
                    : versions.data.items.map((v) => {
                        const active = v.number === shown;
                        return (
                          <li key={v.id}>
                            <button
                              onClick={() => setPicked(v.number === current ? null : v.number)}
                              aria-current={active ? "true" : undefined}
                              className={cn(
                                "w-full rounded-lg px-3 py-2.5 text-left transition-colors duration-[120ms] hover:bg-muted",
                                active && "bg-primary-soft",
                              )}
                            >
                              <span className="flex items-center gap-2">
                                <span className="tnum text-[13px] font-semibold text-foreground">Version {v.number}</span>
                                {v.number === current && <Badge variant="success">Latest</Badge>}
                                <span className="flex-1" />
                                <span className="flex items-center gap-1 text-[12px] text-muted-foreground">
                                  {v.by_agent ? <Bot size={12} aria-hidden="true" /> : <User size={12} aria-hidden="true" />}
                                  {v.by_agent ? "Agent" : "You"}
                                </span>
                              </span>
                              <span className="mt-0.5 block truncate text-[12px] text-foreground/80">
                                {v.rolled_back_from ? `Restored version ${v.rolled_back_from}` : v.message || "No note"}
                              </span>
                              <span className="tnum mt-0.5 block text-[12px] text-subtle">
                                {ago(v.created_at)} · {v.file_count} {v.file_count === 1 ? "file" : "files"} · {bytes(v.total_bytes)}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                </ul>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>

      <UploadSheet
        open={uploading}
        pageId={id}
        pageTitle={p?.title}
        onClose={() => setUploading(false)}
        onDone={async (r) => {
          setUploading(false);
          setPicked(null);
          await refresh();
          setNotice(r.created ? `Published version ${r.version.number}.` : "Nothing changed, so no new version was made.");
        }}
      />

      <Sheet
        open={!!rollback}
        onOpenChange={(o) => {
          if (!o) {
            setRollback(null);
            setFailed("");
          }
        }}
        title={rollback ? `Restore version ${rollback.number}?` : "Restore version"}
        description="This publishes a copy of that version as the newest one. Nothing is deleted."
      >
        {failed && <p role="alert" className="mb-3 text-[13px] text-destructive">{failed}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setRollback(null)}>Cancel</Button>
          <Button onClick={doRollback}>Restore version</Button>
        </div>
      </Sheet>

      {p && isOwner && (
        <ShareSheet open={sharing} onClose={() => setSharing(false)} page={p} onPageChanged={async () => { await page.mutate(); }} />
      )}

      <Sheet
        open={leaving}
        onOpenChange={(o) => {
          if (!o) {
            setLeaving(false);
            setFailed("");
          }
        }}
        title={p ? `Leave "${p.title}"?` : "Leave page"}
        description="You will lose access. The owner can invite you again."
      >
        {failed && <p role="alert" className="mb-3 text-[13px] text-destructive">{failed}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setLeaving(false)}>Cancel</Button>
          <Button variant="destructive" onClick={doLeave}>Leave page</Button>
        </div>
      </Sheet>

      <Sheet
        open={deleting}
        onOpenChange={(o) => {
          if (!o) {
            setDeleting(false);
            setFailed("");
          }
        }}
        title={p ? `Delete "${p.title}"?` : "Delete page"}
        description="The page and its link stop working. Its slug becomes free to use again."
      >
        {failed && <p role="alert" className="mb-3 text-[13px] text-destructive">{failed}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDeleting(false)}>Cancel</Button>
          <Button variant="destructive" onClick={doDelete}>Delete page</Button>
        </div>
      </Sheet>
    </div>
  );
}

function Title({ page, canRename, onSaved }: { page: Page; canRename: boolean; onSaved: () => void | Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(page.title);
  const [slug, setSlug] = useState(page.slug);
  const [error, setError] = useState("");
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) ref.current?.select();
  }, [editing]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (title === page.title && slug === page.slug) return setEditing(false);
    try {
      await api(`/v1/pages/${page.id}`, { method: "PATCH", body: { title: title.trim(), slug: slug.trim() } });
      setEditing(false);
      setError("");
      await onSaved();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!canRename) {
    return (
      <h1 className="flex min-w-0 items-center gap-2 px-2 py-1">
        <span className="truncate text-[15px] font-semibold text-foreground">{page.title}</span>
        <span className="hidden text-[12px] font-normal text-subtle sm:inline">by @{page.owner_handle}</span>
      </h1>
    );
  }

  if (!editing) {
    return (
      <h1 className="min-w-0">
        <button
          onClick={() => {
            setTitle(page.title);
            setSlug(page.slug);
            setEditing(true);
          }}
          className="group flex min-w-0 items-center gap-2 rounded-md px-2 py-1 text-left hover:bg-muted"
        >
          <span className="truncate text-[15px] font-semibold text-foreground">{page.title}</span>
          <span className="hidden font-mono text-[12px] font-normal text-subtle sm:inline">{page.slug}</span>
          <span className="sr-only">Rename page</span>
          <Pencil size={13} aria-hidden="true" className="text-subtle opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
        </button>
      </h1>
    );
  }

  return (
    <form onSubmit={save} className="flex flex-wrap items-center gap-2" noValidate>
      <input
        ref={ref}
        aria-label="Title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="h-8 w-48 rounded-md border border-input-border bg-card px-2 text-[13px] text-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25"
      />
      <input
        aria-label="Slug"
        value={slug}
        onChange={(e) => setSlug(e.target.value)}
        className="h-8 w-40 rounded-md border border-input-border bg-card px-2 font-mono text-[12px] text-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25"
      />
      <Button size="sm" type="submit">Save</Button>
      <Button size="sm" type="button" variant="ghost" onClick={() => { setEditing(false); setError(""); }}>Cancel</Button>
      {error && <span role="alert" className="text-[12px] text-destructive">{error}</span>}
    </form>
  );
}
