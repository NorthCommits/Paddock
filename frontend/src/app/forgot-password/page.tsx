"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthLayout } from "@/components/AuthLayout";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { authClient } from "@/lib/auth/client";

export default function Page() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const mail = email.trim();
    if (!/^\S+@\S+\.\S+$/.test(mail)) return setError("Enter the email address you signed up with.");
    setBusy(true);
    setError("");
    // The answer is the same whether or not an account exists, so nobody can probe for accounts.
    await authClient.emailOtp.sendVerificationOtp({ email: mail, type: "forget-password" }).catch(() => undefined);
    router.push(`/reset-password?email=${encodeURIComponent(mail)}`);
  }

  return (
    <AuthLayout>
      <h1 className="text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">Reset your password</h1>
      <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
        Enter your email and we will send you a code to choose a new password.
      </p>
      <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
        <Field id="email" type="email" label="Email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        {error && (
          <p role="alert" className="rounded-md bg-muted px-3 py-2 text-[13px] text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" className="mt-1 w-full" disabled={busy}>
          {busy ? "Sending code" : "Send code"}
        </Button>
      </form>
      <p className="mt-6 text-[13px] text-muted-foreground">
        Remembered it?{" "}
        <Link className="font-medium text-primary hover:underline" href="/login">
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}
