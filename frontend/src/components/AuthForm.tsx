"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { mutate } from "swr";
import { ApiError, api, setCsrf } from "@/lib/api";
import type { Me } from "@/lib/api";
import { Fence, GateMark, Wordmark } from "./brand";
import { Button } from "./ui/button";
import { Field } from "./ui/input";

const ease = [0.2, 0, 0, 1] as const;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const signup = mode === "signup";

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
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
    <div className="grid min-h-dvh lg:grid-cols-[1fr_1fr]">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Link href="/" aria-label="Paddock home" className="w-fit">
          <Wordmark size={22} />
        </Link>
        <div className="flex flex-1 items-center">
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
                    label="Handle"
                    autoComplete="username"
                    required
                    hint="3 to 30 letters, numbers or dashes."
                  />
                </>
              )}
              <Field id="email" name="email" type="email" label="Email" autoComplete="email" required />
              <Field
                id="password"
                name="password"
                type="password"
                label="Password"
                autoComplete={signup ? "new-password" : "current-password"}
                required
                hint={signup ? "At least 10 characters." : undefined}
              />
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
        </div>
      </div>

      <aside
        aria-hidden="true"
        className="dots relative hidden overflow-hidden border-l border-border bg-primary-soft lg:flex lg:flex-col lg:justify-between lg:p-12"
      >
        <GateMark className="absolute -right-10 top-16 size-[420px] text-primary/15" />
        <div />
        <div className="relative max-w-[26ch]">
          <p className="text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground">
            Your agents publish. You decide what happens next.
          </p>
          <p className="mt-3 text-[15px] leading-[22px] text-muted-foreground">
            Pages, comments and every version, in one calm place.
          </p>
        </div>
        <Fence className="relative mt-10" />
      </aside>
    </div>
  );
}
