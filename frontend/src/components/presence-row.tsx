"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { Person } from "@/lib/api";
import { initials, ringColor } from "@/lib/presence";
import { cn } from "@/lib/utils";

const MAX = 5;

export function Avatar({ person, me, className }: { person: Person; me?: boolean; className?: string }) {
  const name = person.display_name || `@${person.handle}`;
  return (
    <span
      title={me ? `${name} (you)` : name}
      aria-label={me ? `${name}, you` : name}
      role="img"
      style={{ backgroundColor: ringColor(person.id) }}
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white ring-2",
        me ? "ring-foreground" : "ring-background",
        className,
      )}
    >
      {initials(person)}
    </span>
  );
}

/** The people looking at this page right now, you first. */
export function PresenceRow({ pageId, meId, onPick }: { pageId: string; meId?: string; onPick?: (id: string) => void }) {
  const people = useSWR(["people", pageId], () => api<{ items: Person[] }>(`/v1/pages/${pageId}/people`), {
    refreshInterval: 30_000,
    shouldRetryOnError: false,
  });
  const here = (people.data?.items ?? []).filter((p) => p.here);
  here.sort((a, b) => Number(b.id === meId) - Number(a.id === meId));
  if (here.length === 0) return null;
  const shown = here.slice(0, MAX);
  const extra = here.length - shown.length;
  return (
    <div role="group" aria-label={`${here.length} here now`} className="flex items-center -space-x-1.5">
      {shown.map((p) =>
        onPick && p.id !== meId ? (
          <button
            key={p.id}
            type="button"
            onClick={() => onPick(p.id)}
            aria-label={`Chat with ${p.display_name || p.handle}`}
            title={`Chat with ${p.display_name || p.handle}`}
            className="rounded-full transition-transform hover:z-10 hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
          >
            <Avatar person={p} />
          </button>
        ) : (
          <Avatar key={p.id} person={p} me={p.id === meId} />
        ),
      )}
      {extra > 0 && (
        <span
          title={here.slice(MAX).map((p) => p.display_name || `@${p.handle}`).join(", ")}
          className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-semibold text-foreground ring-2 ring-background"
        >
          +{extra}
        </span>
      )}
    </div>
  );
}
