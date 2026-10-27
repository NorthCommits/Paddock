"use client";

import { AnimatePresence, motion } from "motion/react";
import { Bot, FileText, Plus, Trash2, User } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import useSWR from "swr";
import { GateMark } from "@/components/brand";
import { UploadSheet } from "@/components/upload-sheet";
import { Badge } from "@/components/ui/badge";
import { Button, LinkButton } from "@/components/ui/button";
import { Sheet } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { WakeHint } from "@/components/wake-hint";
import { ROLE_LABEL, api } from "@/lib/api";
import type { Page, PageList } from "@/lib/api";
import { ago } from "@/lib/format";

const ghosts = [
  { t: "Q3 revenue report", m: "v3 · 2 comments" },
  { t: "Onboarding flow mockup", m: "v1 · 1 request" },
  { t: "Launch checklist", m: "v5 · up to date" },
];

function Empty({ onNew }: { onNew: () => void }) {
  return (
    <div className="mt-6 grid items-center gap-10 rounded-xl border border-border bg-card p-8 shadow-card md:grid-cols-[1fr_300px]">
      <div>
        <GateMark className="size-14 text-foreground" />
        <h2 className="mt-5 text-[22px] font-semibold leading-7 tracking-[-0.01em] text-foreground">
          The gate is open, the paddock is empty
        </h2>
        <p className="mt-2 max-w-[40ch] text-[15px] leading-[22px] text-muted-foreground">
          Pages appear here as soon as one of your agents publishes. You can also upload a page yourself.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <LinkButton href="/connect" size="lg">Connect an agent</LinkButton>
          <Button size="lg" variant="secondary" onClick={onNew}>Upload a page</Button>
        </div>
      </div>
      <div aria-hidden="true">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.06em] text-subtle">What you will see</p>
        <ul className="space-y-2">
          {ghosts.map((g, i) => (
            <motion.li
              key={g.t}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 0.7 - i * 0.15, x: 0 }}
              transition={{ delay: 0.3 + i * 0.12, duration: 0.5, ease: [0.2, 0, 0, 1] }}
              className="flex items-center gap-3 rounded-lg border border-dashed border-border px-3 py-2.5"
            >
              <FileText size={16} className="text-subtle" />
              <div>
                <p className="text-[13px] font-medium text-foreground">{g.t}</p>
                <p className="text-[12px] text-muted-foreground">{g.m}</p>
              </div>
            </motion.li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Pages() {
  const router = useRouter();
  const params = useSearchParams();
  const { data, error, mutate } = useSWR("pages", () => api<PageList>("/v1/pages?limit=100"));
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<Page | null>(null);
  const [failed, setFailed] = useState("");

  useEffect(() => {
    if (params.get("new") === "1") setUploading(true);
  }, [params]);

  async function remove() {
    if (!deleting) return;
    try {
      await api(`/v1/pages/${deleting.id}`, { method: "DELETE" });
      setDeleting(null);
      await mutate();
    } catch (err) {
      setFailed((err as Error).message);
    }
  }

  return (
    <>
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] font-semibold leading-7 tracking-[-0.01em] text-foreground">Pages</h1>
        {data && data.items.length > 0 && (
          <Button onClick={() => setUploading(true)}>
            <Plus aria-hidden="true" /> New page
          </Button>
        )}
      </div>

      {error ? (
        <p role="alert" className="mt-6 text-[13px] text-destructive">{(error as Error).message}</p>
      ) : !data ? (
        <div className="mt-6 space-y-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <WakeHint />
        </div>
      ) : data.items.length === 0 ? (
        <Empty onNew={() => setUploading(true)} />
      ) : (
        <ul className="mt-6 divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-card">
          <AnimatePresence initial={false}>
            {data.items.map((p, i) => (
              <motion.li
                key={p.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ delay: i * 0.04, duration: 0.3, ease: [0.2, 0, 0, 1] }}
                className="group relative flex items-center gap-3 px-4 py-3 transition-colors duration-[120ms] hover:bg-muted/60"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary">
                  <FileText size={18} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/pages/${p.id}`}
                    className="block truncate text-[15px] font-medium text-foreground after:absolute after:inset-0 after:content-['']"
                  >
                    {p.title}
                  </Link>
                  <p className="mt-0.5 flex items-center gap-1.5 truncate text-[12px] text-muted-foreground">
                    <span className="font-mono">{p.slug}</span>
                    {p.role !== "owner" && (
                      <>
                        <span aria-hidden="true">·</span>
                        <span>by @{p.owner_handle}</span>
                      </>
                    )}
                    <span aria-hidden="true">·</span>
                    <span>Updated {ago(p.updated_at)}</span>
                  </p>
                </div>
                {p.current_version && (
                  <div className="flex shrink-0 items-center gap-2">
                    {p.role !== "owner" && <Badge>{ROLE_LABEL[p.role]}</Badge>}
                    <Badge>
                      {p.current_version.by_agent ? <Bot size={12} aria-hidden="true" /> : <User size={12} aria-hidden="true" />}
                      {p.current_version.by_agent ? "Agent" : "You"}
                    </Badge>
                    <Badge variant="success">v{p.current_version.number}</Badge>
                  </div>
                )}
                {p.role === "owner" && (
                <button
                  aria-label={`Delete ${p.title}`}
                  onClick={() => setDeleting(p)}
                  className="relative z-10 flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-100 transition-opacity hover:bg-border/60 hover:text-destructive md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
                >
                  <Trash2 size={16} />
                </button>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}

      <UploadSheet
        open={uploading}
        onClose={() => setUploading(false)}
        onDone={async (r) => {
          setUploading(false);
          await mutate();
          router.push(`/pages/${r.page.id}`);
        }}
      />

      <Sheet
        open={!!deleting}
        onOpenChange={(o) => {
          if (!o) {
            setDeleting(null);
            setFailed("");
          }
        }}
        title={deleting ? `Delete "${deleting.title}"?` : "Delete page"}
        description="The page and its link stop working. Its slug becomes free to use again."
      >
        {failed && <p role="alert" className="mb-3 text-[13px] text-destructive">{failed}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button variant="destructive" onClick={remove}>Delete page</Button>
        </div>
      </Sheet>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Pages />
    </Suspense>
  );
}
