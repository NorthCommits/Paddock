"use client";

import { useRouter } from "next/navigation";
import useSWR from "swr";
import { api, fetchMe, setCsrf } from "@/lib/api";
import { Button, Skeleton } from "@/components/ui";

export default function Page() {
  const router = useRouter();
  const { data: me } = useSWR("me", fetchMe);

  async function signOut() {
    await api("/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    setCsrf(null);
    router.push("/login");
  }

  const rows = me
    ? [
        ["Name", me.user.display_name],
        ["Handle", `@${me.user.handle}`],
        ["Email", me.user.email],
      ]
    : [];

  return (
    <div className="max-w-[640px]">
      <h1 className="text-[22px] font-semibold leading-7 text-ink">Account</h1>
      <dl className="mt-6 divide-y divide-line rounded-lg border border-line bg-surface">
        {me ? (
          rows.map(([k, v]) => (
            <div key={k} className="flex items-center justify-between px-4 py-3">
              <dt className="text-[13px] text-ink-2">{k}</dt>
              <dd className="text-[13px] text-ink">{v}</dd>
            </div>
          ))
        ) : (
          <div className="space-y-3 p-4">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-4 w-56" />
          </div>
        )}
      </dl>
      <div className="mt-6">
        <Button onClick={signOut}>Sign out</Button>
      </div>
    </div>
  );
}
