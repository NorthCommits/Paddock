"use client";

import { FileText, KeyRound, Menu, PlugZap, Search, Settings } from "lucide-react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import useSWR from "swr";
import { ApiError, fetchMe } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Wordmark } from "./brand";
import { Palette } from "./Palette";
import { Skeleton } from "./ui/skeleton";

const nav = [
  { href: "/pages", label: "Pages", icon: FileText },
  { href: "/connect", label: "Connect an agent", icon: PlugZap },
  { href: "/settings/tokens", label: "Tokens", icon: KeyRound },
  { href: "/settings/account", label: "Account", icon: Settings },
];

export function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const { data: me, error } = useSWR("me", fetchMe, { shouldRetryOnError: false });

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) router.replace("/login");
  }, [error, router]);
  useEffect(() => setOpen(false), [path]);

  if (error && !(error instanceof ApiError && error.status === 401)) {
    return (
      <div className="p-8 text-[15px] text-foreground">
        <p role="alert">{error.message}</p>
      </div>
    );
  }

  const initial = (me?.user.display_name || me?.user.handle || "?").slice(0, 1).toUpperCase();

  const sidebar = (
    <nav aria-label="Main" className="flex h-full flex-col gap-0.5 p-3">
      <Link href="/pages" className="mb-4 w-fit px-2 pt-1" aria-label="Paddock home">
        <Wordmark />
      </Link>
      <LayoutGroup id="nav">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = path === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex h-8 items-center gap-2 rounded-md px-2 text-[13px] transition-colors duration-[120ms]",
                active ? "font-medium text-foreground" : "text-muted-foreground hover:bg-border/50 hover:text-foreground",
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-md bg-card shadow-card"
                  transition={{ type: "spring", stiffness: 500, damping: 40 }}
                />
              )}
              <Icon size={16} aria-hidden="true" className={cn("relative", active && "text-primary")} />
              <span className="relative">{label}</span>
            </Link>
          );
        })}
      </LayoutGroup>
      <div className="mt-auto flex items-center gap-2.5 rounded-md px-2 py-2">
        {me ? (
          <>
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[12px] font-semibold text-primary">
              {initial}
            </span>
            <div className="min-w-0">
              <p className="truncate text-[13px] font-medium text-foreground">{me.user.display_name}</p>
              <p className="truncate text-[12px] text-muted-foreground">@{me.user.handle}</p>
            </div>
          </>
        ) : (
          <Skeleton className="h-8 w-32" />
        )}
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-dvh bg-muted">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 border-r border-border bg-background/70 backdrop-blur-xl md:block">
        {sidebar}
      </aside>
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-30 bg-black/30 md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          >
            <motion.div
              className="h-full w-60 border-r border-border bg-background"
              initial={{ x: -240 }}
              animate={{ x: 0 }}
              exit={{ x: -240 }}
              transition={{ duration: 0.32, ease: [0.32, 0.72, 0, 1] }}
              onClick={(e) => e.stopPropagation()}
            >
              {sidebar}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-border bg-background/70 px-4 backdrop-blur-xl">
          <button
            className="-ml-2 flex size-11 items-center justify-center rounded-md text-muted-foreground hover:bg-border/50 md:hidden"
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <Menu size={18} />
          </button>
          <span className="flex-1" />
          <button
            className="flex h-7 items-center gap-2 rounded-md border border-border bg-card px-2.5 text-[12px] text-muted-foreground transition-colors duration-[120ms] hover:text-foreground"
            onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
          >
            <Search size={14} aria-hidden="true" />
            Search commands
            <kbd className="rounded-sm bg-muted px-1 font-mono text-[11px]">Cmd K</kbd>
          </button>
        </header>
        <main className="mx-auto w-full max-w-[960px] px-6 py-8">{children}</main>
      </div>
      <Palette />
    </div>
  );
}
