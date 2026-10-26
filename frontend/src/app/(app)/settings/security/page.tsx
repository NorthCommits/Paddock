"use client";

import { Laptop } from "lucide-react";
import { useState } from "react";
import useSWR from "swr";
import { Section } from "@/components/section";
import { PasswordField } from "@/components/password-field";
import { Button } from "@/components/ui/button";
import { fetchMe } from "@/lib/api";
import { authClient } from "@/lib/auth/client";
import { authMessage } from "@/lib/auth/session";

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
      const { error } = await authClient.changePassword({
        currentPassword: current,
        newPassword: next,
        revokeOtherSessions: true,
      });
      if (error) throw error;
      setRound((r) => r + 1);
      setMsg({ ok: true, text: "Password changed. Other devices were signed out." });
    } catch (err) {
      setMsg({ ok: false, text: authMessage(err as { message?: string }) });
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

function Devices() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function signOutOthers() {
    setBusy(true);
    setMsg(null);
    const { error } = await authClient.revokeOtherSessions();
    setBusy(false);
    setMsg(error ? { ok: false, text: authMessage(error) } : { ok: true, text: "Signed out of all other devices." });
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-card">
      <p className="min-w-0 flex-1 text-[13px] text-muted-foreground">
        Sign out everywhere except this device. Useful if you used a shared computer.
      </p>
      <Button variant="secondary" onClick={signOutOthers} disabled={busy}>
        <Laptop aria-hidden="true" /> {busy ? "Signing out" : "Sign out other devices"}
      </Button>
      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={msg.ok ? "w-full text-[13px] text-primary" : "w-full text-[13px] text-destructive"}>
          {msg.text}
        </p>
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
      <Section title="Other devices" hint="Browsers that are signed in to your account.">
        <Devices />
      </Section>
    </>
  );
}
