"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthLayout } from "@/components/AuthLayout";
import { PasswordField } from "@/components/password-field";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { authClient } from "@/lib/auth/client";
import { authMessage } from "@/lib/auth/session";

function Reset() {
  const router = useRouter();
  const email = useSearchParams().get("email") ?? "";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const otp = String(f.get("code") ?? "").trim();
    const next = String(f.get("next") ?? "");
    const again = String(f.get("again") ?? "");
    if (!/^\d{4,8}$/.test(otp)) return setError("Enter the code from the email.");
    if (next.length < 10) return setError("Use a password of at least 10 characters.");
    if (next !== again) return setError("The two passwords do not match.");
    setBusy(true);
    setError("");
    try {
      const { error } = await authClient.emailOtp.resetPassword({ email, otp, password: next });
      if (error) throw error;
      router.push(`/login?reset=1&email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(authMessage(err as { message?: string }));
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">Choose a new password</h1>
      <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
        Enter the code we sent to {email || "your email"}, then pick something you do not use anywhere else.
      </p>
      <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
        <Field id="code" name="code" label="Code" inputMode="numeric" autoComplete="one-time-code" maxLength={8} />
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
