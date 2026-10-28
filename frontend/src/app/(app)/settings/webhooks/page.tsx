"use client";

import * as Checkbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import useSWR from "swr";
import { GateMark } from "@/components/brand";
import { CopyField } from "@/components/copy-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/dialog";
import { Field } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, EVENT_GROUPS, api } from "@/lib/api";
import type { Delivery, WebhookCreated, WebhookRow } from "@/lib/api";
import { ago } from "@/lib/format";

const summary = (types: string[]) =>
  types.length === 0 ? "Every event" : types.length === 1 ? types[0] : `${types.length} event types`;

function Webhooks() {
  const params = useSearchParams();
  const { data, error, mutate } = useSWR("webhooks", () => api<WebhookRow[]>("/v1/webhooks"));
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<WebhookCreated | null>(null);
  const [removing, setRemoving] = useState<WebhookRow | null>(null);
  const [failed, setFailed] = useState("");

  useEffect(() => {
    if (params.get("new") === "1") setCreating(true);
  }, [params]);

  async function toggle(h: WebhookRow) {
    try {
      await api(`/v1/webhooks/${h.id}`, { method: "PATCH", body: { active: !h.active } });
      await mutate();
    } catch (err) {
      setFailed((err as Error).message);
    }
  }

  async function remove() {
    if (!removing) return;
    try {
      await api(`/v1/webhooks/${removing.id}`, { method: "DELETE" });
      setRemoving(null);
      await mutate();
    } catch (err) {
      setFailed((err as Error).message);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-foreground">Webhooks</h2>
        <Button onClick={() => setCreating(true)}>New webhook</Button>
      </div>
      <p className="mt-2 text-[13px] text-muted-foreground">
        Paddock calls your server with each event on pages you own, signed so you can check it came from Paddock. An agent on a laptop can
        listen on a live stream instead.
      </p>
      {failed && <p role="alert" className="mt-3 text-[13px] text-destructive">{failed}</p>}

      <div className="mt-6">
        {error ? (
          <p role="alert" className="text-[13px] text-destructive">{(error as Error).message}</p>
        ) : !data ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : data.length === 0 ? (
          <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed border-border bg-card px-8 py-12">
            <GateMark className="size-12 text-foreground" />
            <h2 className="text-[17px] font-semibold text-foreground">No webhooks yet</h2>
            <p className="max-w-[44ch] text-[15px] leading-[22px] text-muted-foreground">
              Add the address of a server that should hear about comments, requests and new versions as they happen.
            </p>
            <Button onClick={() => setCreating(true)}>New webhook</Button>
          </div>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-card">
            {data.map((h) => (
              <Row key={h.id} hook={h} onToggle={() => toggle(h)} onRemove={() => setRemoving(h)} />
            ))}
          </ul>
        )}
      </div>

      <CreateSheet
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={async (h) => {
          setCreating(false);
          setCreated(h);
          await mutate();
        }}
      />

      <Sheet
        open={!!created}
        onOpenChange={(o) => !o && setCreated(null)}
        title="Copy your signing secret now"
        description="This is the only time it is shown. Use it to check the signature on each call."
      >
        {created && (
          <div className="space-y-4">
            <CopyField label="signing secret" value={created.secret} wrap />
            <p className="text-[12px] leading-[18px] text-muted-foreground">
              Each call carries X-Paddock-Timestamp and X-Paddock-Signature. The signature is v1= and then the hex HMAC-SHA256 of the timestamp, a dot and
              the raw body, using this secret.
            </p>
            <div className="flex justify-end">
              <Button onClick={() => setCreated(null)}>I have copied it</Button>
            </div>
          </div>
        )}
      </Sheet>

      <Sheet
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title="Delete this webhook?"
        description="Paddock stops calling it and its delivery history is removed."
      >
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setRemoving(null)}>Cancel</Button>
          <Button variant="destructive" onClick={remove}>Delete webhook</Button>
        </div>
      </Sheet>
    </div>
  );
}

function Row({ hook, onToggle, onRemove }: { hook: WebhookRow; onToggle: () => void; onRemove: () => void }) {
  const [open, setOpen] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<Delivery | null>(null);
  const [problem, setProblem] = useState("");
  const history = useSWR(open ? ["deliveries", hook.id] : null, () =>
    api<{ items: Delivery[] }>(`/v1/webhooks/${hook.id}/deliveries?limit=10`),
  );

  async function test() {
    setTesting(true);
    setProblem("");
    try {
      setResult(await api<Delivery>(`/v1/webhooks/${hook.id}/test`, { method: "POST" }));
      await history.mutate();
    } catch (err) {
      setProblem(err instanceof ApiError ? err.message : "Could not send the test.");
    } finally {
      setTesting(false);
    }
  }

  return (
    <li className="px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className={`truncate font-mono text-[12px] ${hook.active ? "text-foreground" : "text-subtle"}`}>{hook.url}</p>
            <Badge variant={hook.active ? "success" : "neutral"}>{hook.active ? "On" : "Off"}</Badge>
          </div>
          <p className="mt-0.5 text-[12px] text-muted-foreground">{summary(hook.event_types)}</p>
        </div>
        <Button size="sm" variant="ghost" onClick={test} disabled={testing}>{testing ? "Sending" : "Send test"}</Button>
        <Button size="sm" variant="ghost" onClick={onToggle}>{hook.active ? "Turn off" : "Turn on"}</Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen((v) => !v)} aria-expanded={open}>History</Button>
        <Button size="sm" variant="ghost" onClick={onRemove}>Delete</Button>
      </div>
      {problem && <p role="alert" className="mt-2 text-[12px] text-destructive">{problem}</p>}
      {result && (
        <p role="status" className="mt-2 text-[12px] text-muted-foreground">
          {result.status === "delivered"
            ? `Test delivered. Your server answered ${result.last_status_code}.`
            : `Test failed: ${result.last_error ?? "no answer"}`}
        </p>
      )}
      {open && (
        <div className="mt-3 rounded-lg border border-border bg-muted p-3">
          {!history.data ? (
            <Skeleton className="h-10 w-full" />
          ) : history.data.items.length === 0 ? (
            <p className="text-[12px] text-muted-foreground">Nothing sent yet.</p>
          ) : (
            <ul className="space-y-1.5">
              {history.data.items.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center gap-2 text-[12px]">
                  <Badge variant={d.status === "delivered" ? "success" : d.status === "failed" ? "destructive" : "neutral"}>
                    {d.status === "pending" ? "Will retry" : d.status === "failed" ? "Failed" : "Delivered"}
                  </Badge>
                  <span className="font-mono text-foreground">{d.event_type}</span>
                  <span className="tnum text-subtle">{ago(d.created_at)}</span>
                  <span className="tnum text-subtle">
                    {d.attempts} {d.attempts === 1 ? "try" : "tries"}
                  </span>
                  {d.last_error && <span className="w-full text-muted-foreground">{d.last_error}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

function CreateSheet({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (h: WebhookCreated) => void | Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const [all, setAll] = useState(true);
  const [types, setTypes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const toggle = (id: string, on: boolean) => setTypes((cur) => (on ? [...cur, id] : cur.filter((t) => t !== id)));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^https?:\/\//i.test(url.trim())) return setError("Enter a full address that starts with https://");
    if (!all && types.length === 0) return setError("Choose at least one event, or pick every event.");
    setBusy(true);
    setError("");
    try {
      const h = await api<WebhookCreated>("/v1/webhooks", {
        method: "POST",
        body: { url: url.trim(), event_types: all ? [] : types },
      });
      setUrl("");
      setTypes([]);
      setAll(true);
      await onCreated(h);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()} title="New webhook" description="Where to send events, and which ones.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field id="webhook-url" label="Address" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/paddock" />
        <fieldset className="space-y-2">
          <legend className="mb-1.5 text-[12px] font-medium text-muted-foreground">Events</legend>
          <label className="flex items-center gap-2 text-[13px] text-foreground">
            <input type="radio" name="events" checked={all} onChange={() => setAll(true)} /> Every event
          </label>
          <label className="flex items-center gap-2 text-[13px] text-foreground">
            <input type="radio" name="events" checked={!all} onChange={() => setAll(false)} /> Only the ones I choose
          </label>
        </fieldset>
        {!all && (
          <div className="max-h-56 space-y-3 overflow-y-auto rounded-lg border border-border p-3">
            {EVENT_GROUPS.map((g) => (
              <fieldset key={g.title} className="space-y-1.5">
                <legend className="mb-1 text-[11px] font-medium text-subtle">{g.title}</legend>
                {g.types.map((t) => (
                  <label key={t.id} className="flex cursor-default items-start gap-2.5">
                    <Checkbox.Root
                      checked={types.includes(t.id)}
                      onCheckedChange={(v) => toggle(t.id, v === true)}
                      className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border border-subtle data-[state=checked]:border-primary data-[state=checked]:bg-primary"
                    >
                      <Checkbox.Indicator>
                        <Check size={12} className="text-primary-foreground" />
                      </Checkbox.Indicator>
                    </Checkbox.Root>
                    <span>
                      <span className="block text-[13px] text-foreground">{t.label}</span>
                      <span className="block font-mono text-[11px] text-subtle">{t.id}</span>
                    </span>
                  </label>
                ))}
              </fieldset>
            ))}
          </div>
        )}
        {error && <p role="alert" className="text-[13px] text-destructive">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Creating webhook" : "Create webhook"}</Button>
        </div>
      </form>
    </Sheet>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Webhooks />
    </Suspense>
  );
}
