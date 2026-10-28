"use client";

import * as Checkbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import useSWR from "swr";
import { ApiError, SCOPES, api } from "@/lib/api";
import type { TokenCreated, TokenRow } from "@/lib/api";
import { AnimatePresence, motion } from "motion/react";
import { GateMark } from "@/components/brand";
import { CopyField } from "@/components/copy-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/dialog";
import { Field } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const fmt = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Never";

function status(t: TokenRow): { label: string; tone: "neutral" | "destructive" | "success" } {
  if (t.revoked_at) return { label: "Revoked", tone: "destructive" };
  if (t.expires_at && new Date(t.expires_at) < new Date()) return { label: "Expired", tone: "destructive" };
  return { label: "Active", tone: "success" };
}

function Tokens() {
  const params = useSearchParams();
  const { data, error, mutate } = useSWR("tokens", () => api<TokenRow[]>("/v1/tokens"));
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<TokenCreated | null>(null);
  const [revoking, setRevoking] = useState<TokenRow | null>(null);

  useEffect(() => {
    if (params.get("new") === "1") setCreating(true);
  }, [params]);

  async function revoke() {
    if (!revoking) return;
    await api(`/v1/tokens/${revoking.id}`, { method: "DELETE" });
    setRevoking(null);
    await mutate();
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-foreground">Agent tokens</h2>
        <Button onClick={() => setCreating(true)}>New token</Button>
      </div>
      <p className="mt-2 text-[13px] text-muted-foreground">Agents use tokens to act for you. Revoke a token to cut off an agent.</p>

      <div className="mt-6">
        {error ? (
          <p role="alert" className="text-[13px] text-destructive">{(error as Error).message}</p>
        ) : !data ? (
          <div className="space-y-2">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : data.length === 0 ? (
          <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed border-border bg-card px-8 py-12">
            <GateMark className="size-12 text-foreground" />
            <h2 className="text-[17px] font-semibold text-foreground">No tokens yet</h2>
            <p className="max-w-[40ch] text-[15px] leading-[22px] text-muted-foreground">
              Create a token to let an agent publish pages and answer requests.
            </p>
            <Button onClick={() => setCreating(true)}>New token</Button>
          </div>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-card">
            <AnimatePresence initial={false}>
            {data.map((t, idx) => {
              const s = status(t);
              const inactive = s.label !== "Active";
              return (
                <motion.li key={t.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.05, duration: 0.35, ease: [0.2, 0, 0, 1] }} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className={`truncate text-[13px] font-medium ${inactive ? "text-subtle" : "text-foreground"}`}>
                        {t.source === "oauth" ? t.name.replace(/ \(connected with sign-in\)$/, "") : t.name}
                      </p>
                      <Badge variant={s.tone}>{s.label}</Badge>
                      {t.source === "oauth" && <Badge>Connected with sign-in</Badge>}
                    </div>
                    <p className="mt-0.5 truncate text-[12px] text-muted-foreground">
                      <span className="font-mono">{t.prefix}</span> · {t.scopes.join(", ")}
                    </p>
                    <p className="tnum mt-0.5 text-[12px] text-subtle">
                      Created {fmt(t.created_at)} · Last used {fmt(t.last_used_at)}
                    </p>
                  </div>
                  {!inactive && (
                    <Button size="sm" variant="ghost" onClick={() => setRevoking(t)}>Revoke</Button>
                  )}
                </motion.li>
              );
            })}
            </AnimatePresence>
          </ul>
        )}
      </div>

      <CreateSheet
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={async (t) => {
          setCreating(false);
          setCreated(t);
          await mutate();
        }}
      />

      <Sheet
        open={!!created}
        onOpenChange={(o) => !o && setCreated(null)}
        title="Copy your token now"
        description="This is the only time the full token is shown. Store it somewhere safe."
      >
        {created && (
          <div className="space-y-4">
            <CopyField label="token" value={created.token} wrap />
            <div className="flex justify-end">
              <Button onClick={() => setCreated(null)}>I have copied it</Button>
            </div>
          </div>
        )}
      </Sheet>

      <Sheet
        open={!!revoking}
        onOpenChange={(o) => !o && setRevoking(null)}
        title={revoking ? `Revoke "${revoking.name}"?` : "Revoke token"}
        description="Agents using this token will stop working. This cannot be undone."
      >
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setRevoking(null)}>Cancel</Button>
          <Button variant="destructive" onClick={revoke}>Revoke token</Button>
        </div>
      </Sheet>
    </div>
  );
}

function CreateSheet({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (t: TokenCreated) => void | Promise<void>;
}) {
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["pages:read", "pages:write"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const toggle = (id: string, on: boolean) =>
    setScopes((cur) => (on ? [...cur, id] : cur.filter((s) => s !== id)));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Give the token a name, such as the agent it is for.");
    if (scopes.length === 0) return setError("Choose at least one scope.");
    setBusy(true);
    setError("");
    try {
      const t = await api<TokenCreated>("/v1/tokens", { method: "POST", body: { name: name.trim(), scopes } });
      setName("");
      await onCreated(t);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()} title="New token" description="Choose a name and what the agent may do.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field id="token-name" label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="My Claude Code" />
        <fieldset className="space-y-2">
          <legend className="mb-1.5 text-[12px] font-medium text-muted-foreground">Scopes</legend>
          {SCOPES.map((s) => (
            <label key={s.id} className="flex cursor-default items-start gap-2.5">
              <Checkbox.Root
                checked={scopes.includes(s.id)}
                onCheckedChange={(v) => toggle(s.id, v === true)}
                className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border border-subtle data-[state=checked]:border-primary data-[state=checked]:bg-primary"
              >
                <Checkbox.Indicator>
                  <Check size={12} className="text-primary-foreground" />
                </Checkbox.Indicator>
              </Checkbox.Root>
              <span>
                <span className="block text-[13px] text-foreground">{s.label}</span>
                <span className="block text-[12px] text-muted-foreground">{s.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {error && <p role="alert" className="text-[13px] text-destructive">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Creating token" : "Create token"}</Button>
        </div>
      </form>
    </Sheet>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Tokens />
    </Suspense>
  );
}
