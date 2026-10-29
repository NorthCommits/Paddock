"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { Section } from "@/components/section";
import { Badge } from "@/components/ui/badge";
import { Button, LinkButton } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api, fetchMe } from "@/lib/api";
import { signOutNow } from "@/lib/auth/session";
import type { User } from "@/lib/api";
import { day } from "@/lib/format";

export default function Page() {
  const router = useRouter();
  const { data: me, mutate } = useSWR("me", fetchMe);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (me) setName(me.user.display_name);
  }, [me]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setMsg({ ok: false, text: "Name cannot be empty." });
    setBusy(true);
    setMsg(null);
    try {
      await api<User>("/v1/me", { method: "PATCH", body: { display_name: name.trim() } });
      await mutate();
      setMsg({ ok: true, text: "Saved." });
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? err.message : "Something went wrong. Try again." });
    } finally {
      setBusy(false);
    }
  }

  const [notifyError, setNotifyError] = useState("");
  async function setNotify(on: boolean) {
    if (!me) return;
    setNotifyError("");
    // Shown at once, then saved. A failure puts the switch back.
    await mutate({ ...me, user: { ...me.user, notify_requests: on } }, { revalidate: false });
    try {
      await api<User>("/v1/me", { method: "PATCH", body: { notify_requests: on } });
    } catch (err) {
      setNotifyError(err instanceof ApiError ? err.message : "Could not save. Try again.");
      await mutate();
    }
  }

  async function signOut() {
    await signOutNow();
    router.push("/login");
  }

  if (!me) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  const initial = (me.user.display_name || me.user.handle).slice(0, 1).toUpperCase();
  const changed = name.trim() !== me.user.display_name;

  return (
    <>
      <div className="mb-8 flex items-center gap-4">
        <span className="flex size-16 items-center justify-center rounded-full bg-primary-soft text-[26px] font-semibold text-primary">
          {initial}
        </span>
        <div>
          <p className="text-[17px] font-semibold text-foreground">{me.user.display_name}</p>
          <p className="text-[13px] text-muted-foreground">@{me.user.handle} · Member since {day(me.user.created_at)}</p>
        </div>
      </div>

      <Section title="Profile" hint="Your name is shown to people you share pages with.">
        <form onSubmit={save} className="space-y-4 rounded-xl border border-border bg-card p-4 shadow-card" noValidate>
          <Field id="display-name" label="Display name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
          <Field id="handle" label="Username" value={`@${me.user.handle}`} readOnly disabled hint="Your username appears in page links and cannot be changed yet." />
          <div>
            <Field id="email" label="Email" value={me.user.email} readOnly disabled />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {me.user.email_verified_at ? (
                <Badge variant="success">Verified {day(me.user.email_verified_at)}</Badge>
              ) : (
                <>
                  <Badge>Not verified</Badge>
                  <LinkButton href={`/verify-email?email=${encodeURIComponent(me.user.email)}&next=/settings/profile`} variant="ghost" size="sm">
                    Enter code
                  </LinkButton>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy || !changed}>{busy ? "Saving" : "Save changes"}</Button>
            {msg && (
              <p role={msg.ok ? "status" : "alert"} className={msg.ok ? "text-[13px] text-primary" : "text-[13px] text-destructive"}>
                {msg.text}
              </p>
            )}
          </div>
        </form>
      </Section>

      <Section title="Email" hint="Agents only act when they are asked, so we tell you when someone is waiting on yours.">
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-card p-4 shadow-card">
          <input
            type="checkbox"
            role="switch"
            checked={me.user.notify_requests}
            onChange={(e) => void setNotify(e.target.checked)}
            className="mt-0.5 size-4 shrink-0 accent-[var(--primary)]"
          />
          <span>
            <span className="block text-[14px] font-medium text-foreground">Email me when someone asks my agent for a change</span>
            <span className="mt-0.5 block text-[13px] text-muted-foreground">
              One email while requests are waiting on a page, with a line to say to your agent. Your own @agent comments never email you.
            </span>
          </span>
        </label>
        {notifyError && <p role="alert" className="mt-2 text-[13px] text-destructive">{notifyError}</p>}
      </Section>

      <Section title="Session">
        <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4 shadow-card">
          <p className="text-[13px] text-muted-foreground">Sign out of Paddock on this device.</p>
          <Button variant="secondary" onClick={signOut}>
            <LogOut aria-hidden="true" /> Sign out
          </Button>
        </div>
      </Section>
    </>
  );
}
