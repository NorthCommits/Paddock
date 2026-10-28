"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const tabs = [
  { href: "/settings/profile", label: "Profile" },
  { href: "/settings/appearance", label: "Appearance" },
  { href: "/settings/security", label: "Security" },
  { href: "/settings/tokens", label: "Tokens" },
  { href: "/settings/webhooks", label: "Webhooks" },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div>
      <h1 className="text-[22px] font-semibold leading-7 tracking-[-0.01em] text-foreground">Settings</h1>
      <nav aria-label="Settings" className="-mx-1 mt-4 flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((t) => {
          const active = path === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative whitespace-nowrap px-3 py-2.5 text-[13px] transition-colors duration-[120ms]",
                active ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
              {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-primary" />}
            </Link>
          );
        })}
      </nav>
      <div className="mt-6 max-w-[640px]">{children}</div>
    </div>
  );
}
