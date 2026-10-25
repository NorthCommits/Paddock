"use client";

import { Laptop } from "lucide-react";
import { useState } from "react";
import useSWR from "swr";
import { Section } from "@/components/section";
import { PasswordField } from "@/components/password-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api, fetchMe } from "@/lib/api";
import type { BrowserSession } from "@/lib/api";
import { agentName, ago } from "@/lib/format";

function ChangePassword() {
  const { data: me } = useSWR("me", fetchMe);
  const [round, setRound] = useState(0); // remounts the fields to clear them
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const current = String(f.get("current") ?? "");
    const next = String(f.get("next") ?? "");
    if (next.length < 10) return setMsg({ ok: false, text: "Use at least 10 characters for the new password." });
    setBusy(true);
    setMsg(null);
    try {
      await api("/v1/me/password", { method: "POST", body: { current_password: current, new_password: next } });
      setRound((r) => r + 1);
      setMsg({ ok: true, text: "Password changed. Other devices were signed out." });
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? err.message : "Something went wrong. Try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-border bg-card p-4 shadow-card" noValidate>
      <PasswordField key={`c${round}`} id="current" name="current" label="Current password" autoComplete="current-password" />
      <PasswordField
        key={`n${round}`}
        id="next"
        name="next"
        label="New password"
        meter
        autoComplete="new-password"
        extras={[me?.user.handle ?? "", me?.user.email.split("@")[0] ?? ""]}
      />
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={busy}>{busy ? "Changing" : "Change password"}</Button>
        {msg && (
          <p role={msg.ok ? "status" : "alert"} className={msg.ok ? "text-[13px] text-primary" : "text-[13px] text-destructive"}>
            {msg.text}
          </p>
        )}
      </div>
    </form>
  );
}

function Sessions() {
  const { data, error, mutate } = useSWR("sessions", () => api<BrowserSession[]>("/v1/me/sessions"));
  const [failed, setFailed] = useState("");

  async function revoke(id: string) {
    setFailed("");
    try {
      await api(`/v1/me/sessions/${id}`, { method: "DELETE" });
      await mutate();
    } catch (err) {
      setFailed((err as Error).message);
    }
  }

  async function revokeOthers() {
    setFailed("");
    try {
      await api("/v1/me/sessions/revoke-others", { method: "POST" });
      await mutate();
    } catch (err) {
      setFailed((err as Error).message);
    }
  }

  if (error) return <p role="alert" className="text-[13px] text-destructive">{(error as Error).message}</p>;
  if (!data) return <Skeleton className="h-16 w-full" />;

  const others = data.filter((s) => !s.current).length;

  return (
    <div>
      <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-card">
        {data.map((s) => (
          <li key={s.id} className="flex items-center gap-3 px-4 py-3">
            <Laptop size={18} aria-hidden="true" className="shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 text-[13px] font-medium text-foreground">
                {agentName(s.user_agent)}
                {s.current && <Badge variant="success">This device</Badge>}
              </p>
              <p className="tnum truncate text-[12px] text-muted-foreground">
                {s.ip ? `${s.ip} · ` : ""}Active {ago(s.last_seen_at)}
              </p>
            </div>
            {!s.current && (
              <Button size="sm" variant="ghost" onClick={() => revoke(s.id)}>Sign out</Button>
            )}
          </li>
        ))}
      </ul>
      {failed && <p role="alert" className="mt-2 text-[13px] text-destructive">{failed}</p>}
      {others > 0 && (
        <div className="mt-3">
          <Button variant="secondary" onClick={revokeOthers}>Sign out of all other devices</Button>
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <>
      <Section title="Password" hint="Changing your password signs you out everywhere else.">
        <ChangePassword />
      </Section>
      <Section title="Where you are signed in" hint="Browsers that currently have access to your account.">
        <Sessions />
      </Section>
    </>
  );
}
