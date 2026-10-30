"use client";

import { Globe, Link2, Lock, MailPlus, Send, Trash2, Users } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import useSWR from "swr";
import { ApiError, api } from "@/lib/api";
import type {
  Invite,
  InviteCreated,
  Member,
  MemberRole,
  Page,
  ShareLinkCreated,
  ShareLinkRow,
  Visibility,
} from "@/lib/api";
import { ago, day } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CopyField } from "./copy-field";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Sheet } from "./ui/dialog";
import { Skeleton } from "./ui/skeleton";

const VISIBILITY: { id: Visibility; label: string; hint: string; icon: typeof Lock }[] = [
  { id: "private", label: "Only you", hint: "Nobody else can open it", icon: Lock },
  { id: "members", label: "People you invite", hint: "Members sign in to open it", icon: Users },
  { id: "link", label: "Anyone with a link", hint: "Share links work, no account needed", icon: Globe },
];

const MESSAGE_MAX = 500;
// Mirrors the server rule: a personal message cannot carry a web address.
const LINK_IN_TEXT = /https?:|www\.|[a-z0-9-]+\.[a-z]{2,}\//i;

const ROLES: { id: MemberRole; label: string }[] = [
  { id: "viewer", label: "Can view" },
  { id: "commenter", label: "Can comment" },
  { id: "editor", label: "Can edit" },
];

function Select({
  label,
  value,
  onChange,
  children,
  className,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "h-8 rounded-md border border-input-border bg-card px-2 text-[13px] text-foreground transition-[border-color,box-shadow] duration-[120ms] hover:border-subtle focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25",
        className,
      )}
    >
      {children}
    </select>
  );
}

function Heading({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-2">
      <h3 className="text-[13px] font-semibold text-foreground">{children}</h3>
      {hint && <p className="text-[12px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function ShareSheet({
  open,
  onClose,
  page,
  onPageChanged,
}: {
  open: boolean;
  onClose: () => void;
  page: Page;
  onPageChanged: () => void | Promise<void>;
}) {
  const base = `/v1/pages/${page.id}`;
  const members = useSWR(open ? ["members", page.id] : null, () => api<Member[]>(`${base}/members`));
  const invites = useSWR(open ? ["invites", page.id] : null, () => api<Invite[]>(`${base}/invites`));
  const links = useSWR(open ? ["links", page.id] : null, () => api<ShareLinkRow[]>(`${base}/links`));

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<MemberRole>("viewer");
  const [message, setMessage] = useState("");
  const [linkRole, setLinkRole] = useState<"viewer" | "commenter">("viewer");
  const [linkDays, setLinkDays] = useState("");
  const [fresh, setFresh] = useState<{ kind: "invite" | "link"; url: string; note: string } | null>(null);
  const [busy, setBusy] = useState("");

  async function run(key: string, work: () => Promise<void>) {
    setBusy(key);
    setError("");
    try {
      await work();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy("");
    }
  }

  const refreshAll = async () => {
    await Promise.all([members.mutate(), invites.mutate(), links.mutate(), onPageChanged()]);
  };

  // The choice shows at once. The save happens behind it, and a failure puts the old choice back.
  const [chosen, setChosen] = useState<Visibility | null>(null);
  const setVisibility = async (v: Visibility) => {
    setChosen(v);
    setError("");
    try {
      await api(base, { method: "PATCH", body: { visibility: v } });
      setNotice("");
      await onPageChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setChosen(null);
    }
  };

  // Lists change on screen first and are fetched again afterwards, which also undoes a failed change.
  async function quickly<T>(list: { mutate: (...a: never[]) => unknown } & { data?: T[] }, change: (rows: T[]) => T[], call: () => Promise<unknown>) {
    const mutate = list.mutate as unknown as (data?: unknown, opts?: unknown) => Promise<unknown>;
    await mutate((rows?: T[]) => (rows ? change(rows) : rows), { revalidate: false });
    try {
      setError("");
      await call();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    }
    await mutate();
  }

  // Creates the invitation and emails it. Sending again to the same address replaces the old link.
  const postInvite = async (to: string, role: MemberRole, words: string) => {
    const r = await api<InviteCreated>(`${base}/invites`, {
      method: "POST",
      body: { email: to, role, ...(words ? { message: words } : {}) },
    });
    setFresh({
      kind: "invite",
      url: r.accept_url,
      note: r.emailed
        ? `Invitation emailed to ${r.email}. You can also send them this link yourself.`
        : `We could not email ${r.email}. Copy the link below and send it to them instead.`,
    });
    await refreshAll();
  };

  const sendInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError("Enter a valid email address.");
    if (LINK_IN_TEXT.test(message)) return setError("A personal message cannot contain links.");
    return run("invite", async () => {
      await postInvite(email.trim(), inviteRole, message.trim());
      setEmail("");
      setMessage("");
    });
  };

  const sendAgain = (i: Invite) =>
    run(`again-${i.id}`, () => postInvite(i.email, i.role as MemberRole, ""));

  const makeLink = () =>
    run("link", async () => {
      const r = await api<ShareLinkCreated>(`${base}/links`, {
        method: "POST",
        body: { role: linkRole, expires_in_days: linkDays ? Number(linkDays) : null },
      });
      setFresh({ kind: "link", url: r.url, note: "Copy it now. For safety the link is shown only once." });
      await refreshAll();
    });

  const changeRole = (m: Member, role: MemberRole) =>
    quickly(members, (rows) => rows.map((x) => (x.user_id === m.user_id ? { ...x, role } : x)), () =>
      api(`${base}/members/${m.user_id}`, { method: "PATCH", body: { role } }),
    );

  const removeMember = (m: Member) =>
    quickly(members, (rows) => rows.filter((x) => x.user_id !== m.user_id), () =>
      api(`${base}/members/${m.user_id}`, { method: "DELETE" }),
    );

  const revokeInvite = (i: Invite) =>
    quickly(invites, (rows) => rows.filter((x) => x.id !== i.id), () => api(`${base}/invites/${i.id}`, { method: "DELETE" }));

  const revokeLink = (l: ShareLinkRow) =>
    quickly(links, (rows) => rows.filter((x) => x.id !== l.id), () => api(`${base}/links/${l.id}`, { method: "DELETE" }));

  const vis = (chosen ?? page.visibility) as Visibility;
  const inactiveLinks = vis !== "link" && (links.data?.length ?? 0) > 0;
  const inactiveMembers = vis === "private" && (members.data?.length ?? 0) > 0;

  return (
    <Sheet
      wide
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setFresh(null);
          setError("");
          onClose();
        }
      }}
      title={`Share "${page.title}"`}
      description="Choose who can open this page and what they can do."
    >
      <div className="space-y-6">
        <section>
          <Heading>Who can open it</Heading>
          <div role="radiogroup" aria-label="Who can open it" className="grid gap-2 sm:grid-cols-3">
            {VISIBILITY.map(({ id, label, hint, icon: Icon }) => {
              const on = vis === id;
              return (
                <button
                  key={id}
                  role="radio"
                  aria-checked={on}
                  onClick={() => !on && setVisibility(id)}
                  className={cn(
                    "flex flex-col items-start gap-1.5 rounded-lg border p-3 text-left transition-[border-color,box-shadow] duration-[120ms] hover:border-subtle ",
                    on ? "border-primary bg-primary-soft ring-[3px] ring-primary/15" : "border-border bg-card",
                  )}
                >
                  <Icon size={16} aria-hidden="true" className={on ? "text-primary" : "text-muted-foreground"} />
                  <span className="text-[13px] font-medium text-foreground">{label}</span>
                  <span className="text-[12px] leading-4 text-muted-foreground">{hint}</span>
                </button>
              );
            })}
          </div>
          {(inactiveMembers || inactiveLinks) && (
            <p className="mt-2 rounded-md bg-muted px-3 py-2 text-[12px] text-muted-foreground">
              {inactiveMembers
                ? "Members and links are switched off while this page is only yours. "
                : "Share links are switched off until you choose Anyone with a link. "}
              Nothing was deleted.
            </p>
          )}
        </section>

        <section>
          <Heading hint="They get an email and must sign in with that address.">Invite people</Heading>
          <form onSubmit={sendInvite} className="flex flex-wrap gap-2" noValidate>
            <input
              aria-label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              autoComplete="off"
              className="h-8 min-w-0 flex-1 basis-48 rounded-md border border-input-border bg-card px-2.5 text-[13px] text-foreground placeholder:text-subtle hover:border-subtle focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25"
            />
            <Select label="Role for the invited person" value={inviteRole} onChange={(v) => setInviteRole(v as MemberRole)}>
              {ROLES.map((r) => (
                <option key={r.id} value={r.id}>{r.label}</option>
              ))}
            </Select>
            <Button type="submit" size="md" disabled={busy === "invite"}>
              <MailPlus aria-hidden="true" /> {busy === "invite" ? "Sending" : "Invite"}
            </Button>
            <div className="basis-full">
              <textarea
                aria-label="Personal message (optional)"
                value={message}
                maxLength={MESSAGE_MAX}
                rows={2}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Add a personal message (optional). It is included in the email."
                className="block w-full resize-y rounded-md border border-input-border bg-card px-2.5 py-1.5 text-[13px] leading-[1.5] text-foreground placeholder:text-subtle hover:border-subtle focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25"
              />
              {message.length > 0 && (
                <p className="tnum mt-1 text-right text-[11px] text-muted-foreground">
                  {message.length} / {MESSAGE_MAX}
                </p>
              )}
            </div>
          </form>

          {fresh?.kind === "invite" && (
            <div className="mt-3 space-y-2" role="status">
              <p className="text-[12px] text-muted-foreground">{fresh.note}</p>
              <CopyField label="invitation link" value={fresh.url} wrap />
            </div>
          )}

          <div className="mt-3">
            {!members.data || !invites.data ? (
              <Skeleton className="h-12 w-full" />
            ) : members.data.length + invites.data.length === 0 ? (
              <p className="text-[12px] text-muted-foreground">Nobody else has access yet.</p>
            ) : (
              <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                {members.data.map((m) => (
                  <li key={m.user_id} className="flex items-center gap-2.5 px-3 py-2">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[12px] font-semibold text-primary">
                      {(m.display_name || m.handle).slice(0, 1).toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-medium text-foreground">{m.display_name}</span>
                      <span className="block truncate text-[12px] text-muted-foreground">@{m.handle} · {m.email}</span>
                    </span>
                    <Select label={`Role for ${m.display_name}`} value={m.role} onChange={(v) => changeRole(m, v as MemberRole)}>
                      {ROLES.map((r) => (
                        <option key={r.id} value={r.id}>{r.label}</option>
                      ))}
                    </Select>
                    <button
                      aria-label={`Remove ${m.display_name}`}
                      onClick={() => removeMember(m)}
                      className="flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-destructive"
                    >
                      <Trash2 size={15} />
                    </button>
                  </li>
                ))}
                {invites.data.map((i) => (
                  <li key={i.id} className="flex items-center gap-2.5 px-3 py-2">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                      <MailPlus size={14} aria-hidden="true" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] text-foreground">{i.email}</span>
                      <span className="block text-[12px] text-muted-foreground">
                        {i.expired ? "Invitation expired" : `Invited, expires ${day(i.expires_at)}`}
                      </span>
                    </span>
                    <Badge>{ROLES.find((r) => r.id === i.role)?.label}</Badge>
                    <button
                      aria-label={`Send the invitation to ${i.email} again`}
                      title="Send again with a fresh link"
                      onClick={() => void sendAgain(i)}
                      disabled={busy === `again-${i.id}`}
                      className="flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
                    >
                      <Send size={15} />
                    </button>
                    <button
                      aria-label={`Revoke invitation for ${i.email}`}
                      onClick={() => revokeInvite(i)}
                      className="flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-destructive"
                    >
                      <Trash2 size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section>
          <Heading hint="Anyone who has the link can open the page. A link never allows editing.">Share links</Heading>
          <div className="flex flex-wrap gap-2">
            <Select label="What link holders can do" value={linkRole} onChange={(v) => setLinkRole(v as "viewer" | "commenter")}>
              <option value="viewer">Can view</option>
              <option value="commenter">Can comment</option>
            </Select>
            <Select label="When the link expires" value={linkDays} onChange={setLinkDays}>
              <option value="">Never expires</option>
              <option value="1">Expires in 1 day</option>
              <option value="7">Expires in 7 days</option>
              <option value="30">Expires in 30 days</option>
            </Select>
            <Button variant="secondary" onClick={makeLink} disabled={busy === "link"}>
              <Link2 aria-hidden="true" /> {busy === "link" ? "Creating" : "Create link"}
            </Button>
          </div>

          {fresh?.kind === "link" && (
            <div className="mt-3 space-y-2" role="status">
              <p className="text-[12px] text-muted-foreground">{fresh.note}</p>
              <CopyField label="share link" value={fresh.url} wrap />
            </div>
          )}

          <div className="mt-3">
            {!links.data ? (
              <Skeleton className="h-10 w-full" />
            ) : links.data.length === 0 ? (
              <p className="text-[12px] text-muted-foreground">No links yet.</p>
            ) : (
              <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                {links.data.map((l) => (
                  <li key={l.id} className="flex items-center gap-2.5 px-3 py-2">
                    <Link2 size={15} aria-hidden="true" className="shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] text-foreground">
                        {l.role === "commenter" ? "Can comment" : "Can view"}
                      </span>
                      <span className="block text-[12px] text-muted-foreground">
                        Created {ago(l.created_at)} ·{" "}
                        {l.expired ? "expired" : l.expires_at ? `expires ${day(l.expires_at)}` : "never expires"}
                      </span>
                    </span>
                    {l.expired && <Badge variant="destructive">Expired</Badge>}
                    <Button size="sm" variant="ghost" onClick={() => revokeLink(l)}>Revoke</Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        {error && <p role="alert" className="text-[13px] text-destructive">{error}</p>}
        {notice && <p role="status" className="text-[13px] text-primary">{notice}</p>}
        <div className="flex justify-end">
          <Button onClick={onClose}>Done</Button>
        </div>
      </div>
    </Sheet>
  );
}
