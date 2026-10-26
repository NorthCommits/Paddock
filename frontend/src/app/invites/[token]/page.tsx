"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { AuthLayout } from "@/components/AuthLayout";
import { Badge } from "@/components/ui/badge";
import { Button, LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, ROLE_LABEL, api, fetchMe } from "@/lib/api";
import { signOutNow } from "@/lib/auth/session";
import type { InvitePreview, Page } from "@/lib/api";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const invite = useSWR(["invite", token], () => api<InvitePreview>(`/v1/invites/${token}`), { shouldRetryOnError: false });
  const me = useSWR("me", fetchMe, { shouldRetryOnError: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const needsHandle = me.error instanceof ApiError && me.error.code === "onboarding_required";
  useEffect(() => {
    if (needsHandle) router.replace(`/welcome?next=${encodeURIComponent(`/invites/${token}`)}`);
  }, [needsHandle, router, token]);

  const here = `/invites/${token}`;
  const next = encodeURIComponent(here);
  const email = invite.data ? encodeURIComponent(invite.data.email) : "";

  async function accept() {
    setBusy(true);
    setError("");
    try {
      const r = await api<Page>(`/v1/invites/${token}/accept`, { method: "POST" });
      router.push(`/pages/${r.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not accept the invitation.");
      setBusy(false);
    }
  }

  async function switchAccount() {
    await signOutNow();
    router.push(`/login?next=${next}&email=${email}`);
  }

  if (invite.error) {
    return (
      <AuthLayout>
        <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-foreground">This invitation is no longer valid</h1>
        <p className="mt-2 text-[14px] text-muted-foreground">
          It may have expired, been used, or been withdrawn. Ask the owner to send a new one.
        </p>
        <LinkButton href="/pages" className="mt-6">Go to your pages</LinkButton>
      </AuthLayout>
    );
  }

  if (!invite.data) {
    return (
      <AuthLayout>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-4 h-16 w-full" />
      </AuthLayout>
    );
  }

  const inv = invite.data;
  const user = me.data?.user;
  const signedIn = !!user;
  const wrongAccount = signedIn && user.email.toLowerCase() !== inv.email.toLowerCase();
  const unverified = signedIn && !wrongAccount && !user.email_verified_at;

  return (
    <AuthLayout>
      <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-foreground">Join "{inv.page_title}"</h1>
      <p className="mt-2 text-[14px] leading-[21px] text-muted-foreground">
        {inv.invited_by} invited <span className="text-foreground">{inv.email}</span> to open this page by @{inv.owner_handle}.
      </p>
      <p className="mt-3"><Badge variant="success">{ROLE_LABEL[inv.role]}</Badge></p>

      <div className="mt-6 space-y-3">
        {needsHandle && (
          <>
            <p className="text-[13px] text-muted-foreground">One more step: pick a username, then come back here to accept.</p>
            <LinkButton href={`/welcome?next=${next}`}>Choose a username</LinkButton>
          </>
        )}

        {!signedIn && !needsHandle && (
          <>
            <p className="text-[13px] text-muted-foreground">Sign in with {inv.email} to accept.</p>
            <div className="flex flex-wrap gap-2">
              <LinkButton href={`/login?next=${next}&email=${email}`}>Log in</LinkButton>
              <LinkButton href={`/signup?next=${next}&email=${email}`} variant="secondary">Create account</LinkButton>
            </div>
          </>
        )}

        {wrongAccount && (
          <>
            <p role="alert" className="text-[13px] text-destructive">
              You are signed in as {user.email}, but this invitation is for {inv.email}.
            </p>
            <Button variant="secondary" onClick={switchAccount}>Sign out and switch</Button>
          </>
        )}

        {unverified && (
          <>
            <p className="text-[13px] text-muted-foreground">
              Confirm your email address first, using the code we sent you.
            </p>
            <LinkButton href={`/verify-email?email=${encodeURIComponent(user.email)}&next=${next}`} variant="secondary">
              Enter the code
            </LinkButton>
          </>
        )}

        {signedIn && !wrongAccount && !unverified && (
          <Button size="lg" onClick={accept} disabled={busy}>{busy ? "Joining" : "Accept invitation"}</Button>
        )}

        {error && <p role="alert" className="text-[13px] text-destructive">{error}</p>}
      </div>
      <p className="mt-8 text-[12px] text-subtle">
        <Link href="/" className="hover:underline">Paddock</Link> keeps every version of every page.
      </p>
    </AuthLayout>
  );
}
