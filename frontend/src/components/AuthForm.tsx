"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { mutate } from "swr";
import { ApiError, api, setCsrf } from "@/lib/api";
import type { Me } from "@/lib/api";
import { Button, Field, Wordmark } from "./ui";

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
    <div className="flex min-h-dvh items-center justify-center bg-grouped px-4 py-10">
      <div className="w-full max-w-[400px]">
        <div className="mb-6">
          <Link href="/" aria-label="Paddock home">
            <Wordmark size={22} />
          </Link>
        </div>
        <div className="rounded-lg border border-line bg-surface p-6">
          <h1 className="text-[22px] font-semibold leading-7 text-ink">{signup ? "Create your account" : "Log in"}</h1>
          <form onSubmit={submit} className="mt-5 space-y-4" noValidate>
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
              <p role="alert" className="text-[13px] text-danger">
                {error}
              </p>
            )}
            <Button type="submit" variant="primary" size="lg" className="w-full" disabled={busy}>
              {busy ? (signup ? "Creating account" : "Logging in") : signup ? "Create account" : "Log in"}
            </Button>
          </form>
        </div>
        <p className="mt-4 text-[13px] text-ink-2">
          {signup ? "Already have an account? " : "New to Paddock? "}
          <Link className="text-accent-ink hover:underline" href={signup ? "/login" : "/signup"}>
            {signup ? "Log in" : "Create an account"}
          </Link>
        </p>
      </div>
    </div>
  );
}
