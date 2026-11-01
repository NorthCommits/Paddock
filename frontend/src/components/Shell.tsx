"use client";

import * as Menu_ from "@radix-ui/react-dropdown-menu";
import * as Tip from "@radix-ui/react-tooltip";
import { ChevronsUpDown, FileText, PanelLeftClose, PanelLeftOpen, LogOut, Menu, Monitor, Moon, PlugZap, Search, Settings, Sun } from "lucide-react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import useSWR from "swr";
import { ApiError, fetchMe } from "@/lib/api";
import { signOutNow } from "@/lib/auth/session";
import { useSidebarRail } from "@/lib/sidebar";
import { useModKey } from "@/lib/shortcut";
import { forgetTheme, useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { Mark, Wordmark } from "./brand";
import { NotificationBell } from "./notification-bell";
import { Palette } from "./Palette";
import { LinkButton } from "./ui/button";
import { Skeleton } from "./ui/skeleton";

const nav = [
  { href: "/pages", label: "Pages", icon: FileText },
  { href: "/connect", label: "Connect an agent", icon: PlugZap },
  { href: "/settings/profile", label: "Settings", icon: Settings },
];

export function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const { data: me, error } = useSWR("me", fetchMe, { shouldRetryOnError: false });
  const [theme, setTheme] = useTheme();
  const mod = useModKey();
  const [rail, toggleRail] = useSidebarRail();

  useEffect(() => {
    if (!(error instanceof ApiError)) return;
    if (error.status === 401) {
      forgetTheme(); // no one is signed in, so follow the device
      router.replace("/login");
    }
    if (error.code === "onboarding_required") router.replace(`/welcome?next=${encodeURIComponent(path)}`);
  }, [error, router, path]);
  useEffect(() => setOpen(false), [path]);

  const redirecting = error instanceof ApiError && (error.status === 401 || error.code === "onboarding_required");
  if (error && !redirecting) {
    return (
      <div className="p-8 text-[15px] text-foreground">
        <p role="alert">{error.message}</p>
      </div>
    );
  }

  const wide = /^\/pages\/[^/]+$/.test(path);

  async function signOut() {
    await signOutNow();
    router.push("/login");
  }

  const initial = (me?.user.display_name || me?.user.handle || "?").slice(0, 1).toUpperCase();

  // The icon rail is only for the desktop sidebar; the phone drawer always shows labels.
  const sidebarFor = (narrow: boolean) => (
    <nav aria-label="Main" className={cn("flex h-full flex-col gap-0.5 p-3", narrow && "items-center")}>
      <div className={cn("mb-4 flex w-full items-center pt-1", narrow ? "flex-col gap-3" : "justify-between pl-2")}>
        <Link href="/pages" aria-label="Paddock home">
          {narrow ? <Mark size={24} /> : <Wordmark tone="band" />}
        </Link>
        <RailTip label={narrow ? "Expand sidebar" : "Collapse sidebar"} shortcut={`${mod}+B`} show>
          <button
            type="button"
            onClick={toggleRail}
            aria-label={narrow ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!narrow}
            className="hidden size-8 items-center justify-center rounded-md text-band-muted transition-colors duration-[var(--dur-fast)] hover:bg-white/10 hover:text-band-foreground focus-visible:ring-2 focus-visible:ring-band-foreground md:flex"
          >
            {narrow ? <PanelLeftOpen size={16} aria-hidden="true" /> : <PanelLeftClose size={16} aria-hidden="true" />}
          </button>
        </RailTip>
      </div>
      <LayoutGroup id="nav">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = href === "/pages" ? path === href || path.startsWith("/pages/") : path.startsWith(href.split("/").slice(0, 2).join("/"));
          return (
            <RailTip key={href} label={label} show={narrow}>
            <Link
              href={href}
              aria-label={narrow ? label : undefined}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex h-8 items-center gap-2 rounded-md px-2 text-[13px] transition-colors duration-[120ms]",
                narrow && "size-9 justify-center px-0",
                active ? "font-semibold text-band-foreground" : "text-band-muted hover:bg-white/10 hover:text-band-foreground",
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-md bg-white/12 ring-1 ring-white/15"
                  transition={{ type: "spring", stiffness: 500, damping: 40 }}
                />
              )}
              <Icon size={16} aria-hidden="true" className={cn("relative", active ? "text-signal" : "text-band-muted")} />
              {!narrow && <span className="relative">{label}</span>}
            </Link>
            </RailTip>
          );
        })}
      </LayoutGroup>
      <div className={cn("mt-auto", narrow && "w-full")}>
        {me ? (
          <Menu_.Root>
            <Menu_.Trigger aria-label={narrow ? `Account menu, ${me.user.display_name}` : undefined} className={cn("flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left outline-none transition-colors duration-[120ms] hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-band-foreground data-[state=open]:bg-white/10", narrow && "justify-center px-0")}>
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-signal text-[12px] font-bold text-signal-foreground">
                {initial}
              </span>
              {!narrow && (
                <>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium text-band-foreground">{me.user.display_name}</span>
                    <span className="block truncate text-[12px] text-band-muted">@{me.user.handle}</span>
                  </span>
                  <ChevronsUpDown size={14} aria-hidden="true" className="shrink-0 text-band-muted" />
                </>
              )}
            </Menu_.Trigger>
            <Menu_.Portal>
              <Menu_.Content
                side={narrow ? "right" : "top"}
                align={narrow ? "end" : "start"}
                sideOffset={6}
                className="z-50 w-56 rounded-lg border border-border bg-card p-1 shadow-float data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
              >
                <div className="px-2.5 py-2">
                  <p className="truncate text-[13px] font-medium text-foreground">{me.user.display_name}</p>
                  <p className="truncate text-[12px] text-muted-foreground">{me.user.email}</p>
                </div>
                <Menu_.Separator className="my-1 h-px bg-border" />
                <MenuItem onSelect={() => router.push("/settings/profile")} icon={<Settings />}>Settings</MenuItem>
                <Menu_.Separator className="my-1 h-px bg-border" />
                <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium text-subtle">Theme</p>
                <div className="flex gap-1 px-1.5 pb-1.5">
                  {([["system", Monitor, "System"], ["light", Sun, "Light"], ["dark", Moon, "Dark"]] as const).map(([id, Icon, name]) => (
                    <button
                      key={id}
                      aria-label={`${name} theme`}
                      aria-pressed={theme === id}
                      onClick={() => setTheme(id)}
                      className={cn(
                        "flex h-7 flex-1 items-center justify-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:text-foreground",
                        theme === id ? "bg-muted text-foreground" : "hover:bg-muted/60",
                      )}
                    >
                      <Icon size={14} />
                    </button>
                  ))}
                </div>
                <Menu_.Separator className="my-1 h-px bg-border" />
                <MenuItem onSelect={signOut} icon={<LogOut />}>Sign out</MenuItem>
              </Menu_.Content>
            </Menu_.Portal>
          </Menu_.Root>
        ) : (
          <Skeleton className="m-2 h-8 w-32 bg-white/20" />
        )}
      </div>
    </nav>
  );

  return (
    <Tip.Provider delayDuration={200}>
    <div className="flex min-h-dvh bg-muted">
      <aside
        className={cn(
          "on-band sticky top-0 hidden h-dvh shrink-0 overflow-x-hidden bg-band text-band-foreground transition-[width] duration-[var(--dur-base)] ease-[var(--ease-out)] md:block",
          rail ? "w-16" : "w-60",
        )}
      >
        {sidebarFor(rail)}
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
              className="on-band h-full w-60 bg-band text-band-foreground"
              initial={{ x: -240 }}
              animate={{ x: 0 }}
              exit={{ x: -240 }}
              transition={{ duration: 0.32, ease: [0.32, 0.72, 0, 1] }}
              onClick={(e) => e.stopPropagation()}
            >
              {sidebarFor(false)}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <div className={cn("min-w-0 flex-1", wide && "flex h-dvh flex-col")}>
        <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-border bg-background/70 px-4 backdrop-blur-xl">
          <button
            className="-ml-2 flex size-11 items-center justify-center rounded-md text-muted-foreground hover:bg-border md:hidden"
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <Menu size={18} />
          </button>
          <span className="flex-1" />
          {me && <NotificationBell />}
          <button
            className="flex h-7 items-center gap-2 rounded-md border border-border bg-card px-2.5 text-[12px] text-muted-foreground transition-colors duration-[120ms] hover:text-foreground"
            onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
          >
            <Search size={14} aria-hidden="true" />
            Search commands
            <kbd className="rounded-sm bg-muted px-1 font-mono text-[11px]">{mod} K</kbd>
          </button>
        </header>
        {me && !me.user.email_verified_at && (
          <div role="region" aria-label="Email not confirmed" className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border bg-primary-soft px-4 py-2.5">
            <p className="min-w-0 flex-1 text-[13px] text-foreground">
              <span className="font-medium">Confirm your email to publish pages and create tokens.</span>{" "}
              <span className="text-muted-foreground">We sent a code to {me.user.email}.</span>
            </p>
            <LinkButton href={`/verify-email?email=${encodeURIComponent(me.user.email)}&next=${encodeURIComponent(path)}`} variant="secondary" size="sm">
              Enter code
            </LinkButton>
          </div>
        )}
        <main id="main" tabIndex={-1} className={wide ? "min-h-0 w-full flex-1" : "mx-auto w-full max-w-[960px] px-6 py-8"}>{children}</main>
      </div>
      <Palette />
    </div>
    </Tip.Provider>
  );
}

// In the narrow rail a label has no room, so it appears as a tooltip on hover and on keyboard focus.
function RailTip({ label, shortcut, show, children }: { label: string; shortcut?: string; show: boolean; children: ReactNode }) {
  if (!show) return <>{children}</>;
  return (
    <Tip.Root>
      <Tip.Trigger asChild>{children}</Tip.Trigger>
      <Tip.Portal>
        <Tip.Content
          side="right"
          sideOffset={8}
          className="z-50 flex items-center gap-2 rounded-md bg-foreground px-2.5 py-1.5 text-[12px] font-medium text-background shadow-float"
        >
          {label}
          {shortcut && <kbd className="rounded-sm bg-background/20 px-1 font-mono text-[11px]">{shortcut}</kbd>}
        </Tip.Content>
      </Tip.Portal>
    </Tip.Root>
  );
}

function MenuItem({ onSelect, icon, children }: { onSelect: () => void; icon: ReactNode; children: ReactNode }) {
  return (
    <Menu_.Item
      onSelect={onSelect}
      className="flex h-8 cursor-pointer items-center gap-2 rounded-md px-2.5 text-[13px] text-foreground outline-none data-[highlighted]:bg-muted [&_svg]:size-4 [&_svg]:text-muted-foreground"
    >
      {icon}
      {children}
    </Menu_.Item>
  );
}
