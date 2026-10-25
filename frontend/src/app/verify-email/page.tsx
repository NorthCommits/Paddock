"use client";

import { CircleAlert, CircleCheck, Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { mutate } from "swr";
import { AuthLayout } from "@/components/AuthLayout";
import { LinkButton } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

type State = "working" | "ok" | "bad" | "error";

function Verify() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<State>(token ? "working" : "bad");
  const [message, setMessage] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true; // a link works once, so never send it twice
    api("/v1/auth/verify-email", { method: "POST", body: { token } })
      .then(async () => {
        await mutate("me");
        setState("ok");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.code === "invalid_token") setState("bad");
        else {
          setMessage(err instanceof ApiError ? err.message : "Something went wrong.");
          setState("error");
        }
      });
  }, [token]);

  const icon =
    state === "working" ? (
      <Loader2 size={24} aria-hidden="true" className="animate-spin" />
    ) : state === "ok" ? (
      <CircleCheck size={24} aria-hidden="true" />
    ) : (
      <CircleAlert size={24} aria-hidden="true" />
    );

  const copy: Record<State, [string, string]> = {
    working: ["Confirming your email", "One moment."],
    ok: ["Email confirmed", "You can now publish pages and create agent tokens."],
    bad: ["This link has expired", "Confirmation links work for 24 hours and only once. Log in and use the banner to get a new one."],
    error: ["Could not confirm your email", message],
  };

  return (
    <div>
      <span className="flex size-12 items-center justify-center rounded-full bg-primary-soft text-primary">{icon}</span>
      <h1 className="mt-5 text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">{copy[state][0]}</h1>
      <p role="status" className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">{copy[state][1]}</p>
      {state !== "working" && (
        <div className="mt-6">
          <LinkButton href="/pages" size="lg">{state === "ok" ? "Open Paddock" : "Log in"}</LinkButton>
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <AuthLayout>
      <Suspense>
        <Verify />
      </Suspense>
    </AuthLayout>
  );
}
