"use client";

import { useState } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import type { TriggerStatus } from "@/lib/api";
import { ago } from "@/lib/format";

const KEY = "agent-trigger";
const SHAPE = "https://api.anthropic.com/v1/claude_code/routines/trig_.../fire";

/** Saves the address of a Claude Code scheduled task so Paddock can start it when you say yes. */
export function WakeAgent() {
  const { data, mutate } = useSWR<TriggerStatus>(KEY, () => api<TriggerStatus>("/v1/me/agent-trigger"));
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function run(work: () => Promise<string>) {
    setBusy(true);
    setMsg(null);
    try {
      setMsg({ ok: true, text: await work() });
      await mutate();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? err.message : "Something went wrong. Try again." });
    } finally {
      setBusy(false);
    }
  }

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      await api("/v1/me/agent-trigger", { method: "PUT", body: { url: url.trim(), token: token.trim() } });
      setUrl("");
      setToken("");
      return "Saved. Your task starts when you say yes to a request.";
    });
  };
  const test = () =>
    run(async () => {
      const r = await api<{ result: string }>("/v1/me/agent-trigger/test", { method: "POST" });
      return `Test sent: ${r.result}.`;
    });
  const remove = () =>
    run(async () => {
      await api("/v1/me/agent-trigger", { method: "DELETE" });
      return "Removed.";
    });

  if (!data) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-card">
      {data.saved ? (
        <div className="space-y-3">
          <p className="text-[13px] text-foreground">
            A Claude Code task is saved.{" "}
            <span className="text-muted-foreground">
              {data.last_fired_at ? `Last started ${ago(data.last_fired_at)}: ${data.last_result ?? "sent"}.` : "It has not been started yet."}
            </span>
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => void test()}>
              Send a test
            </Button>
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => void remove()}>
              Remove
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={save} className="space-y-3" noValidate>
          <Field id="wake-url" label="Task address" value={url} onChange={(e) => setUrl(e.target.value)} placeholder={SHAPE} hint="From your scheduled task in Claude Code, under API trigger." />
          <Field id="wake-token" label="Task token" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" hint="Stored encrypted and never shown again." />
          <Button type="submit" disabled={busy || !url.trim() || !token.trim()}>
            {busy ? "Saving" : "Save"}
          </Button>
        </form>
      )}
      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={msg.ok ? "mt-3 text-[13px] text-primary" : "mt-3 text-[13px] text-destructive"}>
          {msg.text}
        </p>
      )}
    </div>
  );
}
