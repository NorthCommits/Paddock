"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { Wordmark } from "@/components/brand";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageFrame } from "@/components/page-frame";
import { ROLE_LABEL, api } from "@/lib/api";
import type { Shared, ViewUrl } from "@/lib/api";

const TWELVE_MINUTES = 12 * 60 * 1000; // view links last 15 minutes

export default function SharedPage() {
  const { token } = useParams<{ token: string }>();
  const info = useSWR(["shared", token], () => api<Shared>(`/v1/shared/${token}`), { shouldRetryOnError: false });
  // Asked for in parallel with the page details, not after them.
  const view = useSWR(
    ["shared-view", token],
    () => api<ViewUrl>(`/v1/shared/${token}/view-url`, { method: "POST" }),
    { refreshInterval: TWELVE_MINUTES, revalidateOnFocus: false, shouldRetryOnError: false },
  );

  if (info.error) {
    return (
      <main id="main" className="flex min-h-dvh flex-col items-center justify-center px-6 text-center">
        <Wordmark size={22} />
        <h1 className="mt-8 text-[22px] font-semibold tracking-[-0.02em] text-foreground">This link does not work</h1>
        <p className="mt-2 max-w-[40ch] text-[14px] text-muted-foreground">
          It may have expired or been switched off. Ask the person who shared it for a new link.
        </p>
        <Link href="/login" className="mt-6 text-[13px] text-primary hover:underline">Log in to Paddock</Link>
      </main>
    );
  }

  const s = info.data;
  return (
    <div className="flex h-dvh flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-border bg-background px-4 py-2.5">
        <Link href="/" aria-label="Paddock home"><Wordmark size={18} /></Link>
        {s ? (
          <>
            <span className="truncate text-[15px] font-semibold text-foreground">{s.title}</span>
            <span className="hidden text-[12px] text-muted-foreground sm:inline">Shared by @{s.owner_handle}</span>
            <Badge>{ROLE_LABEL[s.role]}</Badge>
          </>
        ) : (
          <Skeleton className="h-6 w-48" />
        )}
        <span className="flex-1" />
        <Link href={`/login?next=${encodeURIComponent(`/s/${token}`)}`} className="text-[13px] text-primary hover:underline">
          Log in
        </Link>
      </header>
      <div className="relative min-h-0 flex-1 bg-muted">
        {view.error ? (
          <p role="alert" className="p-6 text-[13px] text-destructive">{(view.error as Error).message}</p>
        ) : (
          <PageFrame url={view.data?.url} version={view.data?.version} title={s ? s.title : "Shared page"} />
        )}
      </div>
    </div>
  );
}
