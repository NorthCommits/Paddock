"use client";

import { Menu, PlugZap, Search, Settings, FileText, KeyRound, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import useSWR from "swr";
import { ApiError, fetchMe } from "@/lib/api";
import { Palette } from "./Palette";
import { Skeleton, Wordmark } from "./ui";

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
      <div className="p-8 text-[15px] text-ink">
        <p role="alert">{error.message}</p>
      </div>
    );
  }

  const sidebar = (
    <nav aria-label="Main" className="flex h-full flex-col gap-1 p-3">
      <div className="px-2 pb-4 pt-1">
        <Wordmark />
      </div>
      {nav.map(({ href, label, icon: Icon }) => {
        const active = path === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex h-8 items-center gap-2 rounded-md px-2 text-[13px] transition-colors duration-[120ms] ${
              active ? "bg-line font-medium text-ink" : "text-ink-2 hover:bg-line hover:text-ink"
            }`}
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </Link>
        );
      })}
      <div className="mt-auto flex items-center gap-2 px-2 py-2">
        <UserRound size={16} className="text-ink-2" aria-hidden="true" />
        {me ? (
          <div className="min-w-0">
            <p className="truncate text-[13px] font-medium text-ink">{me.user.display_name}</p>
            <p className="truncate text-[12px] text-ink-2">@{me.user.handle}</p>
          </div>
        ) : (
          <Skeleton className="h-8 w-28" />
        )}
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-dvh bg-grouped">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 border-r border-line bg-sidebar backdrop-blur-xl md:block">
        {sidebar}
      </aside>
      {open && (
        <div className="anim-fade fixed inset-0 z-30 md:hidden" onClick={() => setOpen(false)}>
          <div className="h-full w-60 border-r border-line bg-surface" onClick={(e) => e.stopPropagation()}>
            {sidebar}
          </div>
        </div>
      )}
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-line bg-sidebar px-4 backdrop-blur-xl">
          <button
            className="-ml-2 flex h-11 w-11 items-center justify-center rounded-md text-ink-2 hover:bg-line md:hidden"
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <Menu size={18} />
          </button>
          <span className="flex-1" />
          <button
            className="flex h-7 items-center gap-2 rounded-md bg-line px-2.5 text-[12px] text-ink-2 hover:text-ink"
            onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
          >
            <Search size={14} aria-hidden="true" />
            Search commands
            <kbd className="font-mono text-[11px]">Cmd K</kbd>
          </button>
        </header>
        <main className="mx-auto w-full max-w-[960px] px-6 py-8">{children}</main>
      </div>
      <Palette />
    </div>
  );
}
