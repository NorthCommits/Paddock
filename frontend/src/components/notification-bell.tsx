"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { Button } from "@/components/ui/button";
import { ApiError, api, approveRequest, declineRequest } from "@/lib/api";
import type { AppNotification, NotificationList } from "@/lib/api";
import { ago } from "@/lib/format";
import { cn } from "@/lib/utils";

const KEY = "notifications";

export function useNotifications() {
  // Quiet polling: a person who leaves the tab open still sees a colleague's ask within seconds.
  return useSWR<NotificationList>(KEY, () => api<NotificationList>("/v1/notifications"), {
    refreshInterval: 15000,
    revalidateOnFocus: true,
  });
}

/** Says yes or no for the signed-in person. Returns a message when something needs saying. */
export function useAnswer() {
  const { mutate } = useSWRConfig();
  async function answer(requestId: string, yes: boolean): Promise<{ text: string; link?: boolean } | null> {
    try {
      if (yes) await approveRequest(requestId);
      else await declineRequest(requestId);
      return null;
    } catch (err) {
      if (err instanceof ApiError && err.code === "no_agent") {
        return { text: "Connect your agent first, then say yes.", link: true };
      }
      if (err instanceof ApiError) return { text: err.message };
      return { text: "Could not save. Try again." };
    } finally {
      await mutate(KEY);
      await mutate((k) => Array.isArray(k) && k[0] === "comments");
    }
  }
  return answer;
}

function Row({ n, onAnswer }: { n: AppNotification; onAnswer: (id: string, yes: boolean) => Promise<{ text: string; link?: boolean } | null> }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ text: string; link?: boolean } | null>(null);
  const r = n.request;
  const asking = n.kind === "agent_offer" && r?.my_offer === "offered" && r.status === "awaiting";

  async function go(yes: boolean) {
    setBusy(true);
    setNote(await onAnswer(r!.id, yes));
    setBusy(false);
  }

  let outcome = "";
  if (n.kind === "agent_offer" && r && !asking) {
    if (r.my_offer === "declined") outcome = "You said not now.";
    else if (r.approved_by_me) outcome = "Your agent has this.";
    else if (r.approved_by) outcome = `${r.approved_by} got there first.`;
    else if (r.status === "dismissed") outcome = "This request was rejected.";
  }

  return (
    <li className={cn("border-b border-border px-3 py-3 last:border-b-0", !n.read && "bg-primary-soft/40")}>
      <p className="text-[13px] leading-[19px] text-foreground">{n.body}</p>
      <p className="mt-0.5 text-[12px] text-muted-foreground">
        {n.page && (
          <Link href={`/pages/${n.page.id}`} className="underline underline-offset-2 hover:no-underline">
            {n.page.title}
          </Link>
        )}
        {n.page && " · "}
        <span className="tnum">{ago(n.created_at)}</span>
      </p>
      {asking && (
        <div className="mt-2 flex items-center gap-2">
          <Button size="sm" disabled={busy} onClick={() => void go(true)}>
            Let my agent do it
          </Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => void go(false)}>
            Not now
          </Button>
        </div>
      )}
      {outcome && <p className="mt-1.5 text-[12px] text-muted-foreground">{outcome}</p>}
      {note && (
        <p role="alert" className="mt-1.5 text-[12px] text-destructive">
          {note.text}{" "}
          {note.link && (
            <Link href="/connect" className="underline underline-offset-2">
              Connect an agent
            </Link>
          )}
        </p>
      )}
    </li>
  );
}

function presence(a: NotificationList["agent"]): string {
  if (!a.connected) return "No agent connected yet.";
  if (a.active) return "Your agent is active now.";
  return a.last_seen_at ? `Your agent was last active ${ago(a.last_seen_at)}.` : "Your agent is connected.";
}

export function NotificationBell() {
  const { data, mutate } = useNotifications();
  const answer = useAnswer();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const unread = data?.unread ?? 0;

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      // Seen is not answered: the buttons stay, only the badge clears.
      await mutate((cur) => cur && { ...cur, unread: 0, items: cur.items.map((i) => ({ ...i, read: true })) }, { revalidate: false });
      await api("/v1/notifications/read", { method: "POST" }).catch(() => undefined);
    }
  }

  return (
    <div ref={box} className="relative">
      <button
        aria-label={unread ? `Notifications, ${unread} new` : "Notifications"}
        aria-expanded={open}
        onClick={() => void toggle()}
        className="relative flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:bg-border hover:text-foreground"
      >
        <Bell size={16} aria-hidden="true" />
        {unread > 0 && (
          <span className="tnum absolute -right-0.5 -top-0.5 flex min-w-4 items-center justify-center rounded-full bg-signal px-1 text-[10px] font-bold leading-4 text-signal-foreground">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 top-10 z-40 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-lg border border-border bg-card shadow-float"
        >
          <div className="border-b border-border px-3 py-2.5">
            <p className="text-[13px] font-semibold text-foreground">Notifications</p>
            {data && <p className="text-[12px] text-muted-foreground">{presence(data.agent)}</p>}
          </div>
          {data && data.items.length > 0 ? (
            <ul className="max-h-96 overflow-y-auto">
              {data.items.map((n) => (
                <Row key={n.id} n={n} onAnswer={answer} />
              ))}
            </ul>
          ) : (
            <p className="px-3 py-6 text-center text-[13px] text-muted-foreground">
              Nothing yet. When someone asks for an agent on your pages, you will see it here.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
