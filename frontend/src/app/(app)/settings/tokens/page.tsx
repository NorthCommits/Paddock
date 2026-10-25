"use client";

import * as Checkbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import useSWR from "swr";
import { ApiError, SCOPES, api } from "@/lib/api";
import type { TokenCreated, TokenRow } from "@/lib/api";
import { Badge, Button, CopyField, EmptyState, Field, Sheet, Skeleton } from "@/components/ui";

const fmt = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Never";

function status(t: TokenRow): { label: string; tone: "neutral" | "danger" | "accent" } {
  if (t.revoked_at) return { label: "Revoked", tone: "danger" };
  if (t.expires_at && new Date(t.expires_at) < new Date()) return { label: "Expired", tone: "danger" };
  return { label: "Active", tone: "accent" };
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
    <div className="max-w-[640px]">
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] font-semibold leading-7 text-ink">Tokens</h1>
        <Button variant="primary" onClick={() => setCreating(true)}>New token</Button>
      </div>
      <p className="mt-2 text-[13px] text-ink-2">Agents use tokens to act for you. Revoke a token to cut off an agent.</p>

      <div className="mt-6">
        {error ? (
          <p role="alert" className="text-[13px] text-danger">{(error as Error).message}</p>
        ) : !data ? (
          <div className="space-y-2">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : data.length === 0 ? (
          <EmptyState
            title="No tokens yet"
            body="Create a token to let an agent publish pages and answer requests."
            action={<Button variant="primary" onClick={() => setCreating(true)}>New token</Button>}
          />
        ) : (
          <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
            {data.map((t) => {
              const s = status(t);
              const inactive = s.label !== "Active";
              return (
                <li key={t.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className={`truncate text-[13px] font-medium ${inactive ? "text-ink-3" : "text-ink"}`}>{t.name}</p>
                      <Badge tone={s.tone}>{s.label}</Badge>
                    </div>
                    <p className="mt-0.5 truncate text-[12px] text-ink-2">
                      <span className="font-mono">{t.prefix}</span> · {t.scopes.join(", ")}
                    </p>
                    <p className="tnum mt-0.5 text-[12px] text-ink-3">
                      Created {fmt(t.created_at)} · Last used {fmt(t.last_used_at)}
                    </p>
                  </div>
                  {!inactive && (
                    <Button size="sm" variant="plain" onClick={() => setRevoking(t)}>Revoke</Button>
                  )}
                </li>
              );
            })}
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
            <CopyField label="token" value={created.token} />
            <div className="flex justify-end">
              <Button variant="primary" onClick={() => setCreated(null)}>I have copied it</Button>
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
          <Button onClick={() => setRevoking(null)}>Cancel</Button>
          <Button variant="danger" onClick={revoke}>Revoke token</Button>
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
          <legend className="mb-1.5 text-[12px] font-medium text-ink-2">Scopes</legend>
          {SCOPES.map((s) => (
            <label key={s.id} className="flex cursor-default items-start gap-2.5">
              <Checkbox.Root
                checked={scopes.includes(s.id)}
                onCheckedChange={(v) => toggle(s.id, v === true)}
                className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border border-ink-3 data-[state=checked]:border-accent data-[state=checked]:bg-accent"
              >
                <Checkbox.Indicator>
                  <Check size={12} className="text-on-accent" />
                </Checkbox.Indicator>
              </Checkbox.Root>
              <span>
                <span className="block text-[13px] text-ink">{s.label}</span>
                <span className="block text-[12px] text-ink-2">{s.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy ? "Creating token" : "Create token"}</Button>
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
