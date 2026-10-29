"use client";

import { ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { AuthLayout } from "@/components/AuthLayout";
import { Button, LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, fetchMe, oauthApprove, oauthPreview } from "@/lib/api";
import type { OAuthRequest } from "@/lib/api";
import { signOutNow } from "@/lib/auth/session";

// What each permission means, in plain words.
const MEANING: Record<string, string> = {
  "pages:read": "See your pages and open them",
  "pages:write": "Publish pages and new versions for you",
  "comments:read": "Read the comments on your pages",
  "comments:write": "Reply to comments",
  "requests:act": "Pick up and finish requests you give it",
};

const BLOCKED_SCHEMES = ["javascript:", "data:", "vbscript:", "blob:", "file:"];

function safeToVisit(target: string): boolean {
  try {
    return !BLOCKED_SCHEMES.includes(new URL(target).protocol.toLowerCase());
  } catch {
    return false;
  }
}

const FIELDS = ["client_id", "redirect_uri", "code_challenge", "code_challenge_method", "response_type", "scope", "state"] as const;

function readRequest(params: URLSearchParams): OAuthRequest | null {
  const clientId = params.get("client_id");
  const redirect = params.get("redirect_uri");
  if (!clientId || !redirect) return null;
  return {
    client_id: clientId,
    redirect_uri: redirect,
    code_challenge: params.get("code_challenge") ?? "",
    code_challenge_method: params.get("code_challenge_method") ?? "",
    response_type: params.get("response_type") ?? "",
    scope: params.get("scope") ?? undefined,
    state: params.get("state") ?? undefined,
  };
}

function Consent() {
  const router = useRouter();
  const params = useSearchParams();
  const request = readRequest(params);
  const here = `/oauth/consent?${FIELDS.flatMap((k) => (params.get(k) === null ? [] : [`${k}=${encodeURIComponent(params.get(k) as string)}`])).join("&")}`;
  const heading = useRef<HTMLHeadingElement>(null);
  const [busy, setBusy] = useState<"" | "allow" | "deny">("");
  const [error, setError] = useState("");
  const [done, setDone] = useState<"" | "allow" | "deny">("");

  const me = useSWR("me", fetchMe, { shouldRetryOnError: false });
  const code = me.error instanceof ApiError ? me.error.code : "";
  const signedOut = me.error instanceof ApiError && me.error.status === 401;
  const needsHandle = code === "onboarding_required";
  const user = me.data?.user;
  const unverified = !!user && !user.email_verified_at;
  const ready = !!user && !unverified && !!request;

  const preview = useSWR(ready ? ["oauth-preview", here] : null, () => oauthPreview(request as OAuthRequest), {
    shouldRetryOnError: false,
    revalidateOnFocus: false,
  });

  const previewSignedOut = preview.error instanceof ApiError && preview.error.status === 401;

  useEffect(() => {
    if (signedOut || previewSignedOut) router.replace(`/login?next=${encodeURIComponent(here)}`);
    if (needsHandle) router.replace(`/welcome?next=${encodeURIComponent(here)}`);
  }, [signedOut, previewSignedOut, needsHandle, router, here]);

  useEffect(() => {
    if (preview.data || preview.error || !request || unverified) heading.current?.focus();
  }, [preview.data, preview.error, request, unverified]);

  async function decide(decision: "allow" | "deny") {
    if (!request) return;
    setBusy(decision);
    setError("");
    try {
      const { redirect_to } = await oauthApprove(request, decision);
      if (!safeToVisit(redirect_to)) throw new Error("unsafe redirect");
      setDone(decision);
      window.location.assign(redirect_to);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not finish. Go back to your app and try again.");
      setBusy("");
    }
  }

  async function switchAccount() {
    await signOutNow();
    router.push(`/login?next=${encodeURIComponent(here)}`);
  }

  const wrong = !request || (preview.error && !(preview.error instanceof ApiError && preview.error.status === 401));

  if (wrong && (me.data || !me.isLoading)) {
    return (
      <AuthLayout>
        <h1 ref={heading} tabIndex={-1} className="text-[24px] font-semibold tracking-[-0.02em] text-foreground outline-none">
          We could not start this connection
        </h1>
        <p role="alert" className="mt-2 text-[14px] leading-[21px] text-muted-foreground">
          This request looks wrong. Go back to your app and try again.
        </p>
        <LinkButton href="/pages" variant="secondary" className="mt-6">Go to your pages</LinkButton>
      </AuthLayout>
    );
  }

  if (unverified && user) {
    return (
      <AuthLayout>
        <h1 ref={heading} tabIndex={-1} className="text-[24px] font-semibold tracking-[-0.02em] text-foreground outline-none">
          Confirm your email first
        </h1>
        <p className="mt-2 text-[14px] leading-[21px] text-muted-foreground">
          Use the code we sent you, then you will come back here to finish connecting.
        </p>
        <LinkButton href={`/verify-email?email=${encodeURIComponent(user.email)}&next=${encodeURIComponent(here)}`} className="mt-6">
          Enter the code
        </LinkButton>
      </AuthLayout>
    );
  }

  if (!preview.data || !user) {
    return (
      <AuthLayout>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-4 h-24 w-full" />
      </AuthLayout>
    );
  }

  const info = preview.data;

  if (done) {
    return (
      <AuthLayout>
        <h1 ref={heading} tabIndex={-1} className="text-[24px] font-semibold tracking-[-0.02em] text-foreground outline-none">
          {done === "allow" ? "You are connected" : "Nothing was shared"}
        </h1>
        <p role="status" className="mt-2 text-[14px] leading-[21px] text-muted-foreground">
          {done === "allow"
            ? `You can go back to ${info.client_name} now. This window can be closed.`
            : `${info.client_name} was not given access. You can close this window.`}
        </p>
        <LinkButton href="/pages" variant="secondary" className="mt-6">Go to your pages</LinkButton>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <span className="flex size-12 items-center justify-center rounded-full bg-primary-soft text-primary">
        <ShieldCheck size={24} aria-hidden="true" />
      </span>
      <h1 ref={heading} tabIndex={-1} className="mt-5 text-[26px] font-semibold leading-8 tracking-[-0.02em] text-foreground outline-none">
        Connect {info.client_name}?
      </h1>
      <p className="mt-1.5 text-[15px] leading-[22px] text-muted-foreground">
        <span className="font-medium text-foreground">{info.client_name}</span> wants to work in your Paddock as{" "}
        <span className="font-medium text-foreground">@{user.handle}</span>.
      </p>

      <h2 className="mt-6 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Allow lets it</h2>
      <ul className="mt-2 space-y-1.5 text-[14px] leading-[21px] text-foreground">
        {info.scopes.map((s) => (
          <li key={s} className="flex gap-2">
            <span aria-hidden="true" className="mt-[9px] size-1.5 shrink-0 rounded-full bg-signal" />
            {MEANING[s] ?? s}
          </li>
        ))}
      </ul>
      <p className="mt-4 text-[13px] leading-5 text-muted-foreground">
        You will return to <span className="font-medium text-foreground">{info.redirect_host}</span>. You can remove this
        connection any time in Settings, then Tokens.
      </p>

      {error && (
        <p role="alert" className="mt-4 rounded-md bg-muted px-3 py-2 text-[13px] text-destructive">
          {error}
        </p>
      )}
      <div className="mt-6 flex flex-wrap gap-2">
        <Button size="lg" onClick={() => decide("allow")} disabled={!!busy}>
          {busy === "allow" ? "Connecting" : "Allow"}
        </Button>
        <Button size="lg" variant="secondary" onClick={() => decide("deny")} disabled={!!busy}>
          {busy === "deny" ? "Declining" : "Deny"}
        </Button>
      </div>
      <p className="mt-6 text-[12px] text-subtle">
        Signed in as {user.email}.{" "}
        <button type="button" onClick={switchAccount} className="underline underline-offset-2 hover:no-underline">
          Not you?
        </button>
      </p>
    </AuthLayout>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Consent />
    </Suspense>
  );
}
