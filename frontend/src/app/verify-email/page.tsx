"use client";

import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthLayout } from "@/components/AuthLayout";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { authClient } from "@/lib/auth/client";
import { authMessage, carryQuery, resetSessionCache, safeNext } from "@/lib/auth/session";

const COOLDOWN = 60;

function Verify() {
  const router = useRouter();
  const params = useSearchParams();
  const email = params.get("email") ?? "";
  const next = safeNext(params.get("next"));
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [wait, setWait] = useState(0);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^\d{4,8}$/.test(code.trim())) return setError("Enter the code from the email.");
    setBusy(true);
    setError("");
    try {
      const { error } = await authClient.emailOtp.verifyEmail({ email, otp: code.trim() });
      if (error) throw error;
      await resetSessionCache();
      const session = await authClient.getSession();
      router.push(session.data ? (next ?? "/pages") : `/login${carryQuery(next, email)}`);
    } catch (err) {
      setError(authMessage(err as { message?: string }));
      setBusy(false);
    }
  }

  async function resend() {
    setError("");
    setNotice("");
    const { error } = await authClient.emailOtp.sendVerificationOtp({ email, type: "email-verification" });
    if (error) return setError(authMessage(error));
    setNotice("A new code is on its way.");
    setWait(COOLDOWN);
  }

  return (
    <AuthLayout>
      <span className="flex size-12 items-center justify-center rounded-full bg-primary-soft text-primary">
        <MailCheck size={24} aria-hidden="true" />
      </span>
      <h1 className="mt-5 text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">Check your email</h1>
      <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
        We sent a code to <span className="font-medium text-foreground">{email || "your email"}</span>. Enter it to confirm
        your address.
      </p>
      <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
        <Field
          id="code"
          label="Code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={8}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\s/g, ""))}
          hint="No email after a minute? Check spam, then ask for a new code."
        />
        {error && (
          <p role="alert" className="rounded-md bg-muted px-3 py-2 text-[13px] text-destructive">
            {error}
          </p>
        )}
        {notice && <p role="status" className="text-[13px] text-primary">{notice}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? "Checking" : "Confirm email"}
        </Button>
        <Button type="button" variant="ghost" onClick={resend} disabled={wait > 0 || !email}>
          {wait > 0 ? `Send a new code in ${wait}s` : "Send a new code"}
        </Button>
      </form>
      <p className="mt-6 text-[13px] text-muted-foreground">
        <Link className="font-medium text-primary hover:underline" href={`/login${carryQuery(next, email)}`}>
          Back to log in
        </Link>
      </p>
    </AuthLayout>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Verify />
    </Suspense>
  );
}
