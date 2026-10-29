"use client";

import { Bot, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { Button, LinkButton } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { TokenRow } from "@/lib/api";

const HIDDEN_KEY = "paddock-add-agent-hidden";

function wasHidden(): boolean {
  try {
    return localStorage.getItem(HIDDEN_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * A small button for people who have not connected an agent yet. It opens a short note and a link to
 * the Connect screen. It disappears once any agent is connected, and can be hidden for good.
 */
export function AddAgentHint() {
  // The same key the Connect and Tokens screens use, so connecting an agent clears this at once.
  const { data } = useSWR("tokens", () => api<TokenRow[]>("/v1/tokens"), { revalidateOnFocus: true });
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(true);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => setHidden(wasHidden()), []);

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

  if (!data || hidden) return null;
  const hasAgent = data.some((t) => !t.revoked_at && !(t.expires_at && new Date(t.expires_at) < new Date()));
  if (hasAgent) return null;

  function hideForGood() {
    try {
      localStorage.setItem(HIDDEN_KEY, "1");
    } catch {
      // Remembering is a convenience only.
    }
    setHidden(true);
  }

  return (
    <div ref={box} className="relative">
      <Button size="sm" variant="secondary" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="dialog">
        <Bot aria-hidden="true" /> Add your agent
      </Button>
      {open && (
        <div
          role="dialog"
          aria-label="Add your agent"
          className="absolute right-0 top-full z-40 mt-2 w-72 rounded-xl border border-border bg-card p-4 shadow-float"
        >
          <button
            type="button"
            aria-label="Close"
            onClick={() => setOpen(false)}
            className="absolute right-2 top-2 flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
          >
            <X size={14} />
          </button>
          <h2 className="pr-6 text-[15px] font-semibold leading-5 text-foreground">Bring your own agent</h2>
          <p className="mt-1.5 text-[14px] leading-[1.5] text-muted-foreground">
            Connect Claude, Codex or another agent to your account. It can then read this page and handle requests when you mention @agent.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <LinkButton href="/connect" size="sm">Connect an agent</LinkButton>
            <Button size="sm" variant="ghost" onClick={hideForGood}>Hide this</Button>
          </div>
        </div>
      )}
    </div>
  );
}
