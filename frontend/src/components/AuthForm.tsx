"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { authClient } from "@/lib/auth/client";
import { authCode, authMessage, carryQuery, resetSessionCache, safeNext } from "@/lib/auth/session";
import { AuthLayout } from "./AuthLayout";
import { Button } from "./ui/button";
import { PasswordField } from "./password-field";
import { Field } from "./ui/input";

const ease = [0.2, 0, 0, 1] as const;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const prefill = params.get("email") ?? "";
  const justReset = params.get("reset") === "1";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState(prefill);
  const signup = mode === "signup";
  const carry = carryQuery(next, prefill);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const mail = String(f.get("email") ?? "").trim();
    const password = String(f.get("password") ?? "");
    const name = String(f.get("name") ?? "").trim();
    if (!/^\S+@\S+\.\S+$/.test(mail)) return setError("Enter a valid email address.");
    if (signup && password.length < 10) return setError("Use a password of at least 10 characters.");
    setBusy(true);
    setError("");
    try {
      if (signup) {
        const { error } = await authClient.signUp.email({ email: mail, password, name: name || mail.split("@")[0] });
        if (error) throw error;
        await resetSessionCache();
        router.push(`/verify-email${carryQuery(next, mail)}`);
        return;
      }
      const { error } = await authClient.signIn.email({ email: mail, password });
      if (error) {
        if (error.status === 403 || authCode(error) === "EMAIL_NOT_VERIFIED") {
          await authClient.emailOtp.sendVerificationOtp({ email: mail, type: "email-verification" }).catch(() => undefined);
          router.push(`/verify-email${carryQuery(next, mail)}`);
          return;
        }
        throw error;
      }
      await resetSessionCache();
      router.push(next ?? "/pages");
    } catch (err) {
      setError(authMessage(err as { message?: string }));
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <motion.div
        className="mx-auto w-full max-w-[380px] py-10"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease }}
      >
        <h1 className="text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">
          {signup ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
          {signup ? "Set up your workspace, then connect your first agent." : "Log in to see what your agents have published."}
        </p>
        {justReset && (
          <p role="status" className="mt-4 rounded-md bg-primary-soft px-3 py-2 text-[13px] text-primary">
            Your password was changed. Log in with the new one.
          </p>
        )}
        <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
          {signup && <Field id="name" name="name" label="Name" autoComplete="name" />}
          <Field id="email" name="email" type="email" label="Email" autoComplete="email" required defaultValue={prefill} onChange={(e) => setEmail(e.target.value)} />
          <div>
            <PasswordField
              id="password"
              name="password"
              meter={signup}
              autoComplete={signup ? "new-password" : "current-password"}
              extras={[email.split("@")[0]]}
            />
            {!signup && (
              <Link href="/forgot-password" className="mt-2 inline-block text-[13px] text-primary hover:underline">
                Forgot password?
              </Link>
            )}
          </div>
          {error && (
            <motion.p
              role="alert"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-md bg-muted px-3 py-2 text-[13px] text-destructive"
            >
              {error}
            </motion.p>
          )}
          <Button type="submit" size="lg" className="mt-1 w-full" disabled={busy}>
            {busy ? (signup ? "Creating account" : "Logging in") : signup ? "Create account" : "Log in"}
          </Button>
        </form>
        <p className="mt-6 text-[13px] text-muted-foreground">
          {signup ? "Already have an account? " : "New to Paddock? "}
          <Link className="font-medium text-primary hover:underline" href={`${signup ? "/login" : "/signup"}${carry}`}>
            {signup ? "Log in" : "Create an account"}
          </Link>
        </p>
      </motion.div>
    </AuthLayout>
  );
}
