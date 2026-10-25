"use client";

import { CircleCheck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthLayout } from "@/components/AuthLayout";
import { PasswordField } from "@/components/password-field";
import { Button, LinkButton } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

function Reset() {
  const token = useSearchParams().get("token") ?? "";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [bad, setBad] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const next = String(f.get("next") ?? "");
    const again = String(f.get("again") ?? "");
    if (next.length < 10) return setError("Use a password of at least 10 characters.");
    if (next !== again) return setError("The two passwords do not match.");
    setBusy(true);
    setError("");
    try {
      await api("/v1/auth/reset-password", { method: "POST", body: { token, new_password: next } });
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.code === "invalid_token") setBad(true);
      else setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!token || bad) {
    return (
      <div>
        <h1 className="text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">This link has expired</h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
          Reset links work for 1 hour and only once. Request a new one to continue.
        </p>
        <div className="mt-6">
          <LinkButton href="/forgot-password" size="lg">Request a new link</LinkButton>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div>
        <span className="flex size-12 items-center justify-center rounded-full bg-primary-soft text-primary">
          <CircleCheck size={24} aria-hidden="true" />
        </span>
        <h1 className="mt-5 text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">Password updated</h1>
        <p role="status" className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
          You were signed out everywhere. Log in with your new password.
        </p>
        <div className="mt-6">
          <LinkButton href="/login" size="lg">Log in</LinkButton>
        </div>
      </div>
    );
  }

  return (
    <>
      <h1 className="text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">Choose a new password</h1>
      <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">Pick something you do not use anywhere else.</p>
      <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
        <PasswordField id="next" name="next" label="New password" meter autoComplete="new-password" />
        <PasswordField id="again" name="again" label="Repeat new password" autoComplete="new-password" />
        {error && (
          <p role="alert" className="rounded-md bg-muted px-3 py-2 text-[13px] text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" className="mt-1 w-full" disabled={busy}>
          {busy ? "Saving" : "Update password"}
        </Button>
      </form>
      <p className="mt-6 text-[13px] text-muted-foreground">
        <Link className="font-medium text-primary hover:underline" href="/login">Back to log in</Link>
      </p>
    </>
  );
}

export default function Page() {
  return (
    <AuthLayout>
      <Suspense>
        <Reset />
      </Suspense>
    </AuthLayout>
  );
}
