"use client";

import { AnimatePresence, motion } from "motion/react";
import { BarChart3, GraduationCap, Palette, Rocket } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useCalm } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { Reveal } from "./motion-bits";

const cases = [
  {
    id: "founder",
    icon: Rocket,
    role: "Founder",
    request: "Write this week's investor update from our metrics and last week's page.",
    reply: "Published v1. Revenue is up, churn is flat, three asks listed.",
    bars: [38, 52, 47, 66, 81],
    note: "Weekly update, ready to share with a link",
  },
  {
    id: "designer",
    icon: Palette,
    role: "Designer",
    request: "Make three pricing page layouts and let the team comment on each.",
    reply: "Published 3 mockups. Comments are open on every section.",
    bars: [70, 45, 88, 30, 56],
    note: "Mockups with line by line comments",
  },
  {
    id: "analyst",
    icon: BarChart3,
    role: "Analyst",
    request: "Refresh the churn dashboard every Monday and flag any drop over 5 percent.",
    reply: "Published v14. One cohort dropped 6 percent, marked on the chart.",
    bars: [60, 58, 61, 55, 49],
    note: "A dashboard that stays current",
  },
  {
    id: "students",
    icon: GraduationCap,
    role: "Study group",
    request: "Build a shared revision tracker for our four exams, with a tick box per topic.",
    reply: "Published a small app. Everyone can tick topics off.",
    bars: [25, 40, 55, 72, 90],
    note: "A small app the whole group uses",
  },
];

/** Role tabs. Each shows the request typed out, the agent's reply, and the page that came back. */
export function UseCases() {
  const calm = useCalm();
  const [i, setI] = useState(0);
  const [typed, setTyped] = useState(cases[0].request.length);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const c = cases[i];

  useEffect(() => {
    if (calm) {
      setTyped(c.request.length);
      return;
    }
    setTyped(0);
    const t = setInterval(() => setTyped((n) => (n >= c.request.length ? n : n + 2)), 22);
    return () => clearInterval(t);
  }, [i, calm, c.request.length]);

  function onKey(e: React.KeyboardEvent, idx: number) {
    let next = idx;
    if (e.key === "ArrowRight") next = (idx + 1) % cases.length;
    else if (e.key === "ArrowLeft") next = (idx + cases.length - 1) % cases.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = cases.length - 1;
    else return;
    e.preventDefault();
    setI(next);
    refs.current[next]?.focus();
  }

  const done = typed >= c.request.length;

  return (
    <section id="use-cases" className="mx-auto max-w-[1200px] px-6 py-24" aria-labelledby="uc-title">
      <Reveal>
        <p className="eyebrow text-primary">Who uses it</p>
        <h2 id="uc-title" className="mt-2 max-w-[22ch] text-[32px] font-bold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
          One loop, <span className="serif-accent text-primary">many</span> kinds of work.
        </h2>
      </Reveal>

      <div role="tablist" aria-label="Use cases" className="mt-10 flex flex-wrap gap-2">
        {cases.map((x, k) => (
          <button
            key={x.id}
            ref={(el) => {
              refs.current[k] = el;
            }}
            role="tab"
            id={`uc-tab-${x.id}`}
            aria-selected={k === i}
            aria-controls="uc-panel"
            tabIndex={k === i ? 0 : -1}
            onClick={() => setI(k)}
            onKeyDown={(e) => onKey(e, k)}
            className={cn(
              "inline-flex h-11 items-center gap-2 rounded-full border px-4 text-[14px] font-medium transition-[background-color,color,transform] duration-200 active:scale-[0.97]",
              k === i
                ? "border-primary bg-primary text-primary-foreground"
                : "border-input-border bg-card text-foreground hover:bg-muted",
            )}
          >
            <x.icon className="size-4" aria-hidden="true" />
            {x.role}
          </button>
        ))}
      </div>

      <div
        id="uc-panel"
        role="tabpanel"
        aria-labelledby={`uc-tab-${c.id}`}
        className="mt-6 grid gap-6 rounded-2xl border border-border bg-card p-6 shadow-card md:grid-cols-2 md:p-8"
      >
        <div>
          <p className="eyebrow text-muted-foreground">You ask your agent</p>
          <p className="mt-3 min-h-[84px] text-[18px] leading-[28px] text-foreground">
            <span aria-hidden="true">{c.request.slice(0, typed)}</span>
            <span className="sr-only">{c.request}</span>
            {!done && <span aria-hidden="true" className="ml-0.5 inline-block h-5 w-[2px] translate-y-1 bg-primary" />}
          </p>
          <AnimatePresence mode="wait">
            {done && (
              <motion.div
                key={c.id}
                initial={calm ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
                className="mt-4 rounded-lg border-l-2 border-primary bg-primary-soft px-4 py-3 text-[14px] leading-[22px] text-foreground"
              >
                <span className="eyebrow block text-muted-foreground">Agent reply</span>
                {c.reply}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="rounded-xl border border-border bg-background p-5" aria-hidden="true">
          <div className="flex items-center justify-between">
            <span className="h-3 w-1/3 rounded-full bg-foreground/80" />
            <span className="eyebrow text-muted-foreground">v1</span>
          </div>
          <div className="mt-6 flex h-32 items-end gap-3">
            {c.bars.map((h, k) => (
              <motion.div
                key={`${c.id}-${k}`}
                className="flex-1 rounded-t-md bg-primary"
                initial={calm ? false : { height: 0 }}
                animate={{ height: `${h}%` }}
                transition={{ duration: 0.7, delay: calm ? 0 : 0.15 + k * 0.08, ease: [0.2, 0, 0, 1] }}
              />
            ))}
          </div>
          <p className="mt-4 text-[13px] text-muted-foreground">{c.note}</p>
        </div>
      </div>
    </section>
  );
}
