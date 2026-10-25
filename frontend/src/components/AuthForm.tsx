"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { mutate } from "swr";
import { ApiError, api, setCsrf } from "@/lib/api";
import type { Me } from "@/lib/api";
import { AuthLayout } from "./AuthLayout";
import { Button } from "./ui/button";
import { PasswordField } from "./password-field";
import { Field } from "./ui/input";

const ease = [0.2, 0, 0, 1] as const;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [handle, setHandle] = useState("");
  const [email, setEmail] = useState("");
  const signup = mode === "signup";

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (signup && String(f.get("password") ?? "").length < 10) {
      setError("Use a password of at least 10 characters.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = signup
        ? {
            email: f.get("email"),
            password: f.get("password"),
            handle: f.get("handle"),
            display_name: (f.get("display_name") as string) || null,
          }
        : { email: f.get("email"), password: f.get("password") };
      const out = await api<{ user: Me["user"]; csrf_token: string }>(`/v1/auth/${mode}`, {
        method: "POST",
        body,
      });
      setCsrf(out.csrf_token);
      await mutate("me", undefined, { revalidate: false });
      router.push("/pages");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
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
        <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
          {signup && (
            <>
              <Field id="display_name" name="display_name" label="Name (optional)" autoComplete="name" />
              <Field
                id="handle"
                name="handle"
                onChange={(e) => setHandle(e.target.value)}
                label="Username"
                autoComplete="username"
                required
                hint="Used in your page links. 3 to 30 letters, numbers or dashes."
              />
            </>
          )}
          <Field id="email" name="email" type="email" label="Email" autoComplete="email" required onChange={(e) => setEmail(e.target.value)} />
          <div>
            <PasswordField
              id="password"
              name="password"
              meter={signup}
              autoComplete={signup ? "new-password" : "current-password"}
              extras={[handle, email.split("@")[0]]}
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
          <Link className="font-medium text-primary hover:underline" href={signup ? "/login" : "/signup"}>
            {signup ? "Log in" : "Create an account"}
          </Link>
        </p>
      </motion.div>
    </AuthLayout>
  );
}
