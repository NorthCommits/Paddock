"use client";

import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import { KeyRound, MessageSquare, FileText } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Reveal } from "./motion-bits";

const steps = [
  { icon: KeyRound, title: "Connect your agent", body: "Create a token with only the scopes it needs. Hand it to Claude Code, Codex, Cursor or any tool that can call an HTTP API." },
  { icon: FileText, title: "It publishes a page", body: "Reports, dashboards, mockups and small apps get a private address. Scripts and images come along in the bundle." },
  { icon: MessageSquare, title: "Comment, mention, repeat", body: "Leave a note and mention @agent. The request reaches your agent live, and a new version comes back." },
];

function Visual({ i }: { i: number }) {
  if (i === 0)
    return (
      <div className="w-full max-w-[380px] rounded-xl border border-border bg-card p-5 shadow-float">
        <p className="text-[13px] font-semibold text-foreground">New token</p>
        <div className="mt-3 rounded-md border border-border bg-muted px-3 py-2 font-mono text-[12px] text-foreground">
          pdk_8f3a<span className="text-subtle">••••••••••••••••</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {["pages:read", "pages:write", "comments:write"].map((s) => (
            <span key={s} className="rounded-full bg-primary-soft px-2 py-0.5 font-mono text-[11px] text-primary">{s}</span>
          ))}
        </div>
        <p className="mt-3 text-[12px] text-muted-foreground">Shown once. Revoke any time.</p>
      </div>
    );
  if (i === 1)
    return (
      <div className="w-full max-w-[380px] rounded-xl border border-border bg-card p-5 shadow-float">
        <div className="flex items-center justify-between">
          <p className="text-[13px] font-semibold text-foreground">Launch plan</p>
          <span className="tnum rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-medium text-primary">v1</span>
        </div>
        <div className="mt-4 space-y-2" aria-hidden="true">
          <div className="h-2 w-4/5 rounded-full bg-border" />
          <div className="h-2 w-full rounded-full bg-border" />
          <div className="h-2 w-3/5 rounded-full bg-border" />
        </div>
        <div className="mt-4 rounded-md bg-muted p-2.5 font-mono text-[11px] text-muted-foreground">
          index.html · app.js · cover.png
        </div>
      </div>
    );
  return (
    <div className="w-full max-w-[380px] rounded-xl border border-border bg-card p-5 shadow-float">
      <div className="flex items-start gap-2.5">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[11px] font-semibold text-primary">M</span>
        <div className="rounded-lg rounded-tl-sm bg-muted px-3 py-2 text-[12px] leading-[17px] text-foreground">
          <span className="font-medium text-primary">@agent</span> make the headline shorter
        </div>
      </div>
      <div className="mt-2.5 flex items-start gap-2.5 pl-8">
        <div className="rounded-lg rounded-tl-sm border border-border px-3 py-2 text-[12px] leading-[17px] text-foreground">
          Published <span className="tnum font-medium">v2</span>. Headline now fits one line.
        </div>
      </div>
    </div>
  );
}

export function How() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const [active, setActive] = useState(0);
  useMotionValueEvent(scrollYProgress, "change", (v) => setActive(Math.min(2, Math.floor(v * 3 * 0.999))));

  return (
    <section aria-labelledby="how" className="bg-muted">
      <div className="mx-auto max-w-[1120px] px-6 pt-24">
        <Reveal>
          <p className="text-[13px] font-medium text-primary">How it works</p>
          <h2 id="how" className="mt-2 text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
            One loop, three moves.
          </h2>
        </Reveal>
      </div>

      {/* Desktop: pinned while you scroll through the steps */}
      <div ref={ref} className="relative mx-auto hidden max-w-[1120px] px-6 md:block" style={{ height: "230vh" }}>
        <div className="sticky top-0 grid h-screen grid-cols-[1fr_420px] items-center gap-16">
          <ol className="space-y-3">
            {steps.map((s, i) => (
              <li key={s.title}>
                <button
                  onClick={() => {
                    const el = ref.current;
                    if (!el) return;
                    const top = el.getBoundingClientRect().top + window.scrollY;
                    window.scrollTo({ top: top + (el.offsetHeight - window.innerHeight) * ((i + 0.5) / 3), behavior: "smooth" });
                  }}
                  className={cn(
                    "w-full rounded-xl border p-5 text-left transition-[background-color,border-color,opacity] duration-300",
                    i === active ? "border-border bg-card shadow-card" : "border-transparent opacity-50 hover:opacity-80",
                  )}
                >
                  <span className="flex items-center gap-3">
                    <span className={cn("flex size-8 items-center justify-center rounded-full transition-colors duration-300", i === active ? "bg-primary text-primary-foreground" : "bg-border text-muted-foreground")}>
                      <s.icon size={16} />
                    </span>
                    <span className="text-[17px] font-semibold text-foreground">{s.title}</span>
                  </span>
                  <span className="mt-2 block pl-11 text-[15px] leading-[22px] text-muted-foreground">{s.body}</span>
                </button>
              </li>
            ))}
          </ol>
          <div className="relative flex h-[300px] items-center justify-center" aria-hidden="true">
            <AnimatePresence mode="wait">
              <motion.div
                key={active}
                className="flex w-full justify-center"
                initial={{ opacity: 0, y: 24, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.35, ease: [0.2, 0, 0, 1] }}
              >
                <Visual i={active} />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Mobile: plain stacked steps */}
      <div className="mx-auto max-w-[1120px] space-y-10 px-6 pb-20 pt-10 md:hidden">
        {steps.map((s, i) => (
          <Reveal key={s.title}>
            <div className="flex items-center gap-3">
              <span className="flex size-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <s.icon size={16} />
              </span>
              <h3 className="text-[17px] font-semibold text-foreground">{s.title}</h3>
            </div>
            <p className="mt-2 text-[15px] leading-[22px] text-muted-foreground">{s.body}</p>
            <div className="mt-4" aria-hidden="true"><Visual i={i} /></div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
