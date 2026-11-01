"use client";

import { MessageCircle, Minus, Send, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { ChatMessage, Person } from "@/lib/api";
import { keyOf } from "@/lib/chat";
import type { Chat } from "@/lib/chat";
import { useCalm } from "@/lib/motion";
import { cn } from "@/lib/utils";

type List = { items: ChatMessage[]; more: boolean };

const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const nameOf = (p: { display_name: string; handle: string }) => p.display_name || `@${p.handle}`;

function Dot({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cn("size-2 rounded-full bg-signal", className)} />;
}

export function ChatBubble({ chat, pageId, meId }: { chat: Chat; pageId: string; meId: string }) {
  const calm = useCalm();
  const { open, setOpen, minimised, setMinimised, selected, select, unread, total } = chat;
  const key = keyOf(selected);

  const people = useSWR(["people", pageId], () => api<{ items: Person[] }>(`/v1/pages/${pageId}/people`), {
    refreshInterval: 30_000,
    shouldRetryOnError: false,
  });
  const others = (people.data?.items ?? []).filter((p) => p.id !== meId);
  const who = others.find((p) => p.id === selected);

  const messages = useSWR(
    open && !minimised ? ["messages", pageId, key] : null,
    () => api<List>(`/v1/pages/${pageId}/messages${selected ? `?with=${selected}` : ""}`),
    { shouldRetryOnError: false },
  );
  // Earlier pages are loaded on request and kept apart from the live page, so a refetch never drops them.
  const [earlier, setEarlier] = useState<{ key: string; items: ChatMessage[]; more: boolean | null }>({ key, items: [], more: null });
  const older = earlier.key === key ? earlier : { key, items: [], more: null };
  const latest = messages.data?.items ?? [];
  const items = [...older.items, ...latest.filter((m) => !older.items.some((o) => o.id === m.id))];
  const more = older.more ?? messages.data?.more ?? false;
  const current = useRef(key);
  current.current = key;

  async function loadEarlier() {
    if (!items[0]) return;
    try {
      const r = await api<List>(`/v1/pages/${pageId}/messages?${new URLSearchParams({ ...(selected ? { with: selected } : {}), before: items[0].id })}`);
      setEarlier({ key, items: [...r.items, ...older.items], more: r.more });
    } catch (err) {
      setError((err as Error).message || "Could not load earlier messages.");
    }
  }

  // One draft for each conversation, so text typed for one person never ends up in another chat.
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const text = drafts[key] ?? "";
  const setDraft = (k: string, v: string) => setDrafts((d) => ({ ...d, [k]: v }));
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [announce, setAnnounce] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const seen = useRef<string | null>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
    const last = items[items.length - 1];
    if (last && seen.current && last.id !== seen.current && last.sender.id !== meId) {
      setAnnounce(`${nameOf(last.sender)}: ${last.body}`);
    }
    seen.current = last?.id ?? null;
  }, [items, meId]);

  useEffect(() => {
    setError("");
    seen.current = null;
  }, [key]);

  // Tell the senders you have read this far, whenever the chat is open and you are looking at it.
  const marked = useRef<Record<string, string>>({});
  const newest = [...items].reverse().find((m) => m.sender.id !== meId && !m.deleted && !m.id.startsWith("pending-"));
  const newestId = newest?.id;
  const looking = open && !minimised;
  useEffect(() => {
    if (!looking || !newestId) return;
    function mark() {
      if (document.visibilityState !== "visible" || !newestId || marked.current[key] === newestId) return;
      marked.current[key] = newestId;
      void api(`/v1/pages/${pageId}/chat-read`, { method: "PUT", body: { up_to: newestId, ...(selected ? { with: selected } : {}) } }).catch(() => {
        delete marked.current[key]; // try again next time
      });
    }
    mark();
    document.addEventListener("visibilitychange", mark);
    return () => document.removeEventListener("visibilitychange", mark);
  }, [looking, newestId, key, pageId, selected]);

  async function send() {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setError("");
    setDraft(key, "");
    const mine: ChatMessage = {
      id: `pending-${Date.now()}`,
      sender: { id: meId, handle: "", display_name: "You" },
      to: selected,
      body,
      created_at: new Date().toISOString(),
      deleted: false,
      seen_by: [],
      audience: 0,
    };
    await messages.mutate(
      async (cur) => {
        try {
          const saved = await api<ChatMessage>(`/v1/pages/${pageId}/messages`, { method: "POST", body: { body, to: selected } });
          return { more: cur?.more ?? false, items: [...(cur?.items ?? []), saved] };
        } catch (err) {
          const reason = (err as Error).message || "Could not send. Try again.";
          setDraft(key, body);
          setError(current.current === key ? reason : `A message to ${who ? nameOf(who) : "everyone"} was not sent. ${reason}`);
          return cur;
        }
      },
      { optimisticData: (cur) => ({ more: cur?.more ?? false, items: [...(cur?.items ?? []), mine] }), rollbackOnError: true, revalidate: false },
    );
    setSending(false);
  }

  async function remove(id: string) {
    try {
      await api(`/v1/messages/${id}`, { method: "DELETE" });
      await messages.mutate();
    } catch (err) {
      setError((err as Error).message || "Could not delete. Try again.");
    }
  }

  const panel = open && !minimised;
  const slide = calm ? { duration: 0 } : { duration: 0.22, ease: [0.32, 0.72, 0, 1] as const };

  return (
    <div className="pointer-events-none absolute bottom-4 right-4 z-20 flex flex-col items-end gap-3 max-[480px]:left-4">
      <AnimatePresence>
        {panel && (
          <motion.div
            key="panel"
            role="dialog"
            aria-label="Page chat"
            initial={calm ? false : { opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={calm ? { opacity: 0 } : { opacity: 0, y: 12, scale: 0.98 }}
            transition={slide}
            onKeyDown={(e) => {
              if (e.key === "Escape") setMinimised(true);
            }}
            className="pointer-events-auto flex h-[min(440px,calc(100%-4rem))] w-[340px] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-float max-[480px]:w-full"
          >
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <p className="truncate text-[13px] font-semibold text-foreground">{who ? nameOf(who) : "Everyone on this page"}</p>
              <button
                aria-label="Minimise chat"
                onClick={() => setMinimised(true)}
                className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <Minus size={16} aria-hidden="true" />
              </button>
            </div>

            <div className="flex gap-1.5 overflow-x-auto border-b border-border px-3 py-2" role="tablist" aria-label="Conversations">
              <Chip label="Everyone" active={selected === null} dot={(unread.all ?? 0) > 0} onClick={() => select(null)} />
              {others.map((p) => (
                <Chip key={p.id} label={nameOf(p)} active={selected === p.id} dot={(unread[p.id] ?? 0) > 0} here={p.here} onClick={() => select(p.id)} />
              ))}
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
              {messages.isLoading && <p className="text-center text-[12px] text-muted-foreground">Loading</p>}
              {!messages.isLoading && items.length === 0 && (
                <p className="px-2 py-6 text-center text-[13px] text-muted-foreground">
                  {who ? `Only you and ${nameOf(who)} can see this.` : "Everyone with access to this page can see this chat."}
                </p>
              )}
              {more && (
                <button onClick={() => void loadEarlier()} className="mx-auto block text-[12px] text-muted-foreground underline underline-offset-2 hover:text-foreground">
                  Load earlier messages
                </button>
              )}
              {items.map((m) => {
                const mineMsg = m.sender.id === meId;
                return (
                  <div key={m.id} className={cn("group flex flex-col", mineMsg ? "items-end" : "items-start")}>
                    <p className="mb-0.5 text-[11px] text-muted-foreground">
                      {mineMsg ? "You" : nameOf(m.sender)} <span className="tnum">{time(m.created_at)}</span>
                    </p>
                    <div
                      className={cn(
                        "max-w-[85%] whitespace-pre-wrap break-words rounded-lg px-2.5 py-1.5 text-[13px] leading-[19px]",
                        m.deleted ? "italic text-muted-foreground" : mineMsg ? "bg-foreground text-background" : "bg-muted text-foreground",
                      )}
                    >
                      {m.deleted ? "Message deleted" : m.body}
                    </div>
                    {mineMsg && !m.deleted && (
                      <Receipt m={m} group={selected === null}>
                        {!m.id.startsWith("pending-") && (
                          <button
                            onClick={() => void remove(m.id)}
                            aria-label="Delete message"
                            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 size={11} aria-hidden="true" /> Delete
                          </button>
                        )}
                      </Receipt>
                    )}
                  </div>
                );
              })}
              <div ref={end} />
            </div>
            <p aria-live="polite" className="sr-only">{announce}</p>

            <div className="border-t border-border p-2">
              {error && <p role="alert" className="mb-1.5 px-1 text-[12px] text-destructive">{error}</p>}
              <div className="flex items-end gap-2">
                <textarea
                  value={text}
                  onChange={(e) => setDraft(key, e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void send();
                    }
                  }}
                  rows={1}
                  maxLength={1000}
                  aria-label={who ? `Message ${nameOf(who)}` : "Message everyone"}
                  placeholder={who ? `Message ${nameOf(who)}` : "Message everyone"}
                  className="max-h-24 min-h-9 flex-1 resize-none rounded-md border border-border bg-background px-2.5 py-2 text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <button
                  aria-label="Send"
                  disabled={!text.trim() || sending}
                  onClick={() => void send()}
                  className="flex size-9 shrink-0 items-center justify-center rounded-md bg-foreground text-background disabled:opacity-40"
                >
                  <Send size={15} aria-hidden="true" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        aria-label={total ? `Page chat, ${total} unread` : "Page chat"}
        aria-expanded={panel}
        onClick={() => {
          if (panel) setMinimised(true);
          else {
            setOpen(true);
            setMinimised(false);
          }
        }}
        className="pointer-events-auto relative flex size-12 items-center justify-center rounded-full bg-foreground text-background shadow-float transition-transform duration-150 hover:scale-105 motion-reduce:transition-none motion-reduce:hover:scale-100"
      >
        <MessageCircle size={20} aria-hidden="true" />
        {total > 0 && (
          <span
            aria-hidden="true"
            className="tnum absolute -right-1 -top-1 flex min-w-5 items-center justify-center rounded-full bg-signal px-1 text-[11px] font-bold leading-5 text-signal-foreground ring-2 ring-background"
          >
            {total > 9 ? "9+" : total}
          </span>
        )}
      </button>
    </div>
  );
}

function Ticks({ double, seen }: { double: boolean; seen: boolean }) {
  return (
    <svg viewBox="0 0 20 12" aria-hidden="true" className={cn("h-3 w-[18px] fill-none stroke-current", seen ? "text-primary" : "text-muted-foreground")} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 6.5l3.2 3.2L11 2.5" />
      {double && <path d="M8.2 8.6l1 1L15.4 2.5" />}
    </svg>
  );
}

// One tick: sent. Two indigo ticks: read. In the page chat they turn indigo only once everyone has
// read it, and tapping them lists who has. `children` (the Delete button) sits beside the ticks.
function Receipt({ m, group, children }: { m: ChatMessage; group: boolean; children?: React.ReactNode }) {
  const [listing, setListing] = useState(false);
  const n = m.seen_by.length;
  const all = m.audience > 0 && n >= m.audience;
  let ticks: React.ReactNode;
  if (m.id.startsWith("pending-")) {
    ticks = <span className="text-[11px] text-muted-foreground">Sending</span>;
  } else if (!group) {
    ticks = (
      <span className="flex items-center gap-1 text-[11px] text-muted-foreground" title={n ? `Read ${time(m.seen_by[0].at)}` : "Sent"}>
        <Ticks double={n > 0} seen={n > 0} />
        <span className="sr-only">{n ? `Read at ${time(m.seen_by[0].at)}` : "Sent"}</span>
      </span>
    );
  } else {
    ticks = (
      <button
        type="button"
        onClick={() => n > 0 && setListing((v) => !v)}
        aria-expanded={n > 0 ? listing : undefined}
        aria-label={n ? `Read by ${n} of ${m.audience}. Show who.` : "Sent"}
        className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
      >
        <Ticks double={n > 0} seen={all} />
        {n > 0 && !all && <span className="tnum" aria-hidden="true">{n}/{m.audience}</span>}
      </button>
    );
  }
  return (
    <div className="mt-0.5 flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        {ticks}
        {children}
      </div>
      {group && listing && n > 0 && (
        <ul className="w-44 space-y-0.5 rounded-md border border-border bg-background p-1.5 text-[11px] text-foreground">
          {m.seen_by.map((s) => (
            <li key={s.id} className="flex justify-between gap-2">
              <span className="truncate">{s.name}</span>
              <span className="tnum shrink-0 text-muted-foreground">{time(s.at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Chip({ label, active, dot, here, onClick }: { label: string; active: boolean; dot: boolean; here?: boolean; onClick: () => void }) {
  return (
    <button
      role="tab"
      aria-selected={active}
      aria-label={dot ? `${label}, unread` : label}
      onClick={onClick}
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px]",
        active ? "border-foreground bg-foreground text-background" : "border-border text-foreground hover:bg-muted",
      )}
    >
      {here && <span aria-hidden="true" className="size-1.5 rounded-full bg-primary" />}
      {label}
      {dot && <Dot />}
    </button>
  );
}
