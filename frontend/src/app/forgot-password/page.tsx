"use client";

import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AuthLayout } from "@/components/AuthLayout";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";

export default function Page() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError("Enter the email address you signed up with.");
    setBusy(true);
    setError("");
    try {
      await api("/v1/auth/forgot-password", { method: "POST", body: { email: email.trim() } });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      {sent ? (
        <div>
          <span className="flex size-12 items-center justify-center rounded-full bg-primary-soft text-primary">
            <MailCheck size={24} aria-hidden="true" />
          </span>
          <h1 className="mt-5 text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">Check your email</h1>
          <p role="status" className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
            If an account exists for <span className="font-medium text-foreground">{email.trim()}</span>, we sent a link to
            reset the password. It works for 1 hour.
          </p>
          <p className="mt-4 text-[13px] text-muted-foreground">
            Nothing arrived? Check your spam folder, or{" "}
            <button className="font-medium text-primary hover:underline" onClick={() => setSent(false)}>
              try again
            </button>
            .
          </p>
          <Link href="/login" className="mt-6 inline-block text-[13px] font-medium text-primary hover:underline">
            Back to log in
          </Link>
        </div>
      ) : (
        <>
          <h1 className="text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">Reset your password</h1>
          <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
            Enter your email and we will send you a link to choose a new password.
          </p>
          <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
            <Field
              id="email"
              type="email"
              label="Email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            {error && (
              <p role="alert" className="rounded-md bg-muted px-3 py-2 text-[13px] text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" className="mt-1 w-full" disabled={busy}>
              {busy ? "Sending link" : "Send reset link"}
            </Button>
          </form>
          <p className="mt-6 text-[13px] text-muted-foreground">
            Remembered it?{" "}
            <Link className="font-medium text-primary hover:underline" href="/login">
              Log in
            </Link>
          </p>
        </>
      )}
    </AuthLayout>
  );
}
