"use client";

import { Check, Sparkles, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { AuthLayout } from "@/components/AuthLayout";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import type { HandleCheck, Onboarding, User } from "@/lib/api";
import { safeNext } from "@/lib/auth/session";
import { mutate } from "swr";

function Welcome() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next")) ?? "/pages";
  const info = useSWR("onboarding", () => api<Onboarding>("/v1/onboarding"), {
    shouldRetryOnError: false,
    revalidateOnFocus: false,
  });
  const [handle, setHandle] = useState("");
  const [name, setName] = useState("");
  const [check, setCheck] = useState<HandleCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const filled = useRef(false);

  useEffect(() => {
    if (info.error instanceof ApiError && info.error.status === 401) router.replace("/login");
  }, [info.error, router]);

  useEffect(() => {
    if (info.data && !info.data.needs_onboarding) router.replace(next);
    if (info.data && !filled.current) {
      filled.current = true;
      setName(info.data.name ?? "");
    }
  }, [info.data, next, router]);

  // Ask the server whether the handle is free, a moment after the person stops typing.
  useEffect(() => {
    const value = handle.trim().toLowerCase();
    if (!value) return setCheck(null);
    const t = setTimeout(async () => {
      try {
        const out = await api<HandleCheck>(`/v1/handles/check?handle=${encodeURIComponent(value)}`);
        setCheck((cur) => (value === handle.trim().toLowerCase() ? out : cur));
      } catch {
        setCheck(null);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [handle]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!handle.trim()) return setError("Choose a username.");
    setBusy(true);
    setError("");
    try {
      await api<User>("/v1/onboarding", {
        method: "POST",
        body: { handle: handle.trim(), display_name: name.trim() || null },
      });
      await mutate("me", undefined, { revalidate: true });
      router.push(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  const status = check
    ? check.available
      ? { ok: true, text: `@${check.handle} is yours to take` }
      : { ok: false, text: check.reason ?? "That handle is not available" }
    : null;

  return (
    <AuthLayout>
      <h1 className="text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">Pick your username</h1>
      <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
        It appears in your page links, like paddock/@you/report. 3 to 30 letters, numbers or dashes.
      </p>
      <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
        <Field id="name" label="Name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        <div>
          <Field
            id="handle"
            label="Username"
            autoComplete="off"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            error={status && !status.ok ? status.text : undefined}
          />
          {status?.ok && (
            <p role="status" className="mt-1.5 flex items-center gap-1 text-[12px] text-primary">
              <Check size={13} aria-hidden="true" /> {status.text}
            </p>
          )}
        </div>

        {info.data && info.data.suggestions.length > 0 && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-muted-foreground">
              <Sparkles size={13} aria-hidden="true" /> Free right now, tap one
            </p>
            <div className="flex flex-wrap gap-2">
              {info.data.suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setHandle(s)}
                  className="rounded-full border border-border bg-card px-3 py-1 text-[13px] text-foreground transition-colors duration-[120ms] hover:border-primary hover:bg-primary-soft"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <p role="alert" className="flex items-center gap-1.5 rounded-md bg-muted px-3 py-2 text-[13px] text-destructive">
            <X size={14} aria-hidden="true" /> {error}
          </p>
        )}
        <Button type="submit" size="lg" className="mt-1 w-full" disabled={busy || (status ? !status.ok : false)}>
          {busy ? "Creating" : "Continue"}
        </Button>
      </form>
    </AuthLayout>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Welcome />
    </Suspense>
  );
}
