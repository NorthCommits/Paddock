"use client";

import { AnimatePresence, motion } from "motion/react";
import { AppWindow, BarChart3, FileText, LayoutDashboard } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Reveal } from "./motion-bits";

const kinds = [
  { id: "reports", icon: FileText, title: "Reports", body: "Research, summaries and write-ups with headings, tables and charts." },
  { id: "dashboards", icon: BarChart3, title: "Dashboards", body: "Numbers and charts your agent refreshes whenever the data changes." },
  { id: "mockups", icon: LayoutDashboard, title: "Mockups", body: "Screens, posters and layouts you can comment on, line by line." },
  { id: "apps", icon: AppWindow, title: "Small apps", body: "Checklists, trackers and tools with scripts, running in a sandbox." },
];

function Checklist() {
  const [done, setDone] = useState([true, false, false]);
  const items = ["Draft the brief", "Review with the team", "Publish v2"];
  return (
    <div className="w-full max-w-[340px] rounded-xl border border-border bg-card p-5 shadow-float">
      <p className="text-[13px] font-semibold text-foreground">Launch checklist</p>
      <p className="mt-0.5 text-[12px] text-muted-foreground">This one really works. Tap an item.</p>
      <ul className="mt-3 space-y-1.5">
        {items.map((t, i) => (
          <li key={t}>
            <button
              onClick={() => setDone((d) => d.map((v, k) => (k === i ? !v : v)))}
              className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-[13px] transition-colors duration-[120ms] hover:bg-muted"
            >
              <span className={cn("flex size-4 items-center justify-center rounded-sm border transition-colors duration-200", done[i] ? "border-primary bg-primary" : "border-subtle")}>
                {done[i] && (
                  <motion.svg viewBox="0 0 12 12" className="size-3" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}>
                    <motion.path d="M2.5 6.5 5 9l4.5-5.5" fill="none" stroke="var(--primary-foreground)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.25 }} />
                  </motion.svg>
                )}
              </span>
              <span className={cn("transition-colors duration-200", done[i] ? "text-subtle line-through" : "text-foreground")}>{t}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Visual({ id }: { id: string }) {
  if (id === "reports")
    return (
      <div className="w-full max-w-[340px] rounded-xl border border-border bg-card p-5 shadow-float" aria-hidden="true">
        <div className="h-3 w-2/3 rounded-full bg-foreground/80" />
        <div className="mt-4 space-y-2">
          {[100, 92, 96, 60].map((w, i) => <div key={i} className="h-2 rounded-full bg-border" style={{ width: `${w}%` }} />)}
        </div>
        <div className="mt-4 rounded-lg border-l-2 border-primary bg-primary-soft px-3 py-2 text-[12px] text-foreground">Key finding: signups doubled after the change.</div>
        <div className="mt-4 space-y-2">
          {[94, 78].map((w, i) => <div key={i} className="h-2 rounded-full bg-border" style={{ width: `${w}%` }} />)}
        </div>
      </div>
    );
  if (id === "dashboards")
    return (
      <div className="w-full max-w-[340px] rounded-xl border border-border bg-card p-5 shadow-float" aria-hidden="true">
        <div className="flex items-center justify-between">
          <p className="text-[13px] font-semibold text-foreground">Service health</p>
          <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground"><span className="size-1.5 animate-pulse rounded-full bg-primary" /> Live</span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {[["Uptime", "99.98%"], ["Latency", "74 ms"]].map(([k, v]) => (
            <div key={k} className="rounded-lg bg-muted p-2.5"><p className="text-[11px] text-muted-foreground">{k}</p><p className="tnum text-[17px] font-semibold text-foreground">{v}</p></div>
          ))}
        </div>
        <svg viewBox="0 0 300 60" className="mt-3 w-full">
          <motion.path d="M0 44 L30 36 L60 40 L90 22 L120 30 L150 14 L180 26 L210 10 L240 20 L270 8 L300 16" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.1 }} />
        </svg>
      </div>
    );
  if (id === "mockups")
    return (
      <div className="w-[200px] rounded-[26px] border-[5px] border-foreground/80 bg-card p-3 shadow-float" aria-hidden="true">
        <div className="mx-auto h-1 w-10 rounded-full bg-border" />
        <div className="mt-3 h-16 rounded-xl bg-primary-soft" />
        <div className="mt-3 h-2.5 w-3/4 rounded-full bg-foreground/80" />
        <div className="mt-2 h-2 w-full rounded-full bg-border" />
        <div className="mt-1.5 h-2 w-5/6 rounded-full bg-border" />
        <div className="mt-4 h-8 rounded-lg bg-primary" />
      </div>
    );
  return <Checklist />;
}

export function Showcase() {
  const [id, setId] = useState("reports");
  return (
    <section aria-labelledby="show" className="mx-auto max-w-[1200px] px-6 py-24">
      <Reveal>
        <p className="eyebrow text-primary">What agents can publish</p>
        <h2 id="show" className="mt-2 max-w-[22ch] text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
          If your agent can build it, Paddock can host it.
        </h2>
      </Reveal>
      <div className="mt-12 grid gap-8 md:grid-cols-[1fr_1fr] md:gap-16">
        <div role="tablist" aria-label="What agents can publish" className="space-y-1.5">
          {kinds.map((k) => (
            <button
              key={k.id}
              role="tab"
              aria-selected={id === k.id}
              onClick={() => setId(k.id)}
              className={cn("relative w-full rounded-xl p-4 text-left transition-colors duration-200", id === k.id ? "" : "hover:bg-muted")}
            >
              {id === k.id && <motion.span layoutId="show-tab" className="absolute inset-0 rounded-xl border border-border bg-card shadow-card" transition={{ type: "spring", stiffness: 480, damping: 38 }} />}
              <span className="relative flex items-center gap-3">
                <k.icon size={18} className={id === k.id ? "text-primary" : "text-muted-foreground"} />
                <span>
                  <span className="block text-[15px] font-semibold text-foreground">{k.title}</span>
                  <span className="mt-0.5 block text-[13px] leading-[18px] text-muted-foreground">{k.body}</span>
                </span>
              </span>
            </button>
          ))}
        </div>
        <div role="tabpanel" className="flex min-h-[320px] items-center justify-center rounded-xl bg-muted dots p-6">
          <AnimatePresence mode="wait">
            <motion.div key={id} initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3, ease: [0.2, 0, 0, 1] }} className="flex w-full justify-center">
              <Visual id={id} />
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
