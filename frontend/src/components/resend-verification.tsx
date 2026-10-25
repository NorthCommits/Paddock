"use client";

import { useEffect, useState } from "react";
import { mutate } from "swr";
import { ApiError, api } from "@/lib/api";
import { Button } from "./ui/button";

// One minute between emails, matching the server.
const COOLDOWN = 60;

export function ResendVerification({ variant = "secondary" }: { variant?: "secondary" | "ghost" }) {
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(0);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  async function send() {
    setBusy(true);
    setMsg(null);
    try {
      await api("/v1/me/verification/resend", { method: "POST" });
      setMsg({ ok: true, text: "Email sent. Check your inbox." });
      setWait(COOLDOWN);
      await mutate("me");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) setWait(COOLDOWN);
      setMsg({ ok: false, text: err instanceof ApiError ? err.message : "Something went wrong. Try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant={variant} onClick={send} disabled={busy || wait > 0}>
        {wait > 0 ? `Resend in ${wait}s` : busy ? "Sending" : "Resend email"}
      </Button>
      {msg && (
        <span role={msg.ok ? "status" : "alert"} className={msg.ok ? "text-[12px] text-primary" : "text-[12px] text-destructive"}>
          {msg.text}
        </span>
      )}
    </span>
  );
}
