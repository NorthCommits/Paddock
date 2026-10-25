"use client";

import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

const bars = [
  { a: 38, b: 14 },
  { a: 52, b: 20 },
  { a: 44, b: 28 },
  { a: 66, b: 22 },
  { a: 58, b: 34 },
  { a: 78, b: 30 },
];

const ease = [0.2, 0, 0, 1] as const;

/** A looping, original illustration of the Paddock loop: comment, mention, new version. */
export function HeroDemo() {
  const reduce = useReducedMotion();
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (reduce) {
      setStep(3);
      return;
    }
    const timers = [
      setTimeout(() => setStep(1), 1400),
      setTimeout(() => setStep(2), 3000),
      setTimeout(() => setStep(3), 5200),
      setTimeout(() => setStep(0), 10200),
    ];
    const loop = setInterval(() => {
      setStep(0);
      setTimeout(() => setStep(1), 1400);
      setTimeout(() => setStep(2), 3000);
      setTimeout(() => setStep(3), 5200);
    }, 10200);
    return () => {
      timers.forEach(clearTimeout);
      clearInterval(loop);
    };
  }, [reduce]);

  const published = step >= 3;
  const versions = published ? ["v1", "v2", "v3"] : ["v1", "v2"];
  const active = published ? "v3" : "v2";

  return (
    <div
      role="img"
      aria-label="Illustration: a person comments on a report and mentions the agent, and the agent publishes version 3 with revenue split by region."
      className="relative w-full max-w-[540px] select-none"
    >
      <div className="rounded-xl border border-border bg-card shadow-float">
        <div className="flex items-center gap-3 border-b border-border px-4 py-2.5">
          <div className="flex gap-1.5">
            <span className="size-2.5 rounded-full bg-border" />
            <span className="size-2.5 rounded-full bg-border" />
            <span className="size-2.5 rounded-full bg-border" />
          </div>
          <div className="flex-1 truncate rounded-md bg-muted px-3 py-1 text-center font-mono text-[11px] text-muted-foreground">
            paddock/swapnil/q3-revenue
          </div>
        </div>

        <div className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[15px] font-semibold text-foreground">Q3 revenue</p>
              <p className="text-[12px] text-muted-foreground">Published by Claude Code</p>
            </div>
            <LayoutGroup>
              <div className="flex gap-1 rounded-md bg-muted p-0.5">
                {versions.map((v) => (
                  <motion.span
                    key={v}
                    layout
                    initial={v === "v3" ? { opacity: 0, scale: 0.8 } : false}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3, ease }}
                    className={cn(
                      "relative rounded-[5px] px-2.5 py-1 text-[12px] font-medium tnum",
                      v === active ? "text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {v === active && (
                      <motion.span
                        layoutId="ver"
                        className="absolute inset-0 rounded-[5px] bg-card shadow-sm"
                        transition={{ type: "spring", stiffness: 500, damping: 38 }}
                      />
                    )}
                    <span className="relative">{v}</span>
                  </motion.span>
                ))}
              </div>
            </LayoutGroup>
          </div>

          <div className="mt-5 flex h-[132px] items-end gap-3 border-b border-border px-1">
            {bars.map((b, i) => (
              <div key={i} className="flex flex-1 flex-col justify-end">
                <motion.div
                  className="rounded-t-[3px] bg-primary/35"
                  initial={false}
                  animate={{ height: published ? b.b : 0 }}
                  transition={{ duration: 0.7, delay: published ? 0.25 + i * 0.05 : 0, ease }}
                />
                <motion.div
                  className="bg-primary"
                  style={{ borderRadius: published ? 0 : "3px 3px 0 0" }}
                  initial={{ height: 0 }}
                  animate={{ height: b.a }}
                  transition={{ duration: 0.7, delay: i * 0.05, ease }}
                />
              </div>
            ))}
          </div>
          <div className="mt-2 flex justify-between px-1 font-mono text-[10px] text-subtle">
            <span>Jul</span>
            <span>Aug</span>
            <span>Sep</span>
          </div>

          <div className="mt-4 min-h-[112px] space-y-2.5">
            <AnimatePresence initial={false}>
              {step >= 1 && (
                <motion.div
                  key="comment"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.32, ease }}
                  className="flex items-start gap-2.5"
                >
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[11px] font-semibold text-primary">
                    M
                  </span>
                  <div className="rounded-lg rounded-tl-sm bg-muted px-3 py-2 text-[12px] leading-[17px] text-foreground">
                    <span className="font-medium text-primary">@agent</span> can you split revenue by region?
                  </div>
                </motion.div>
              )}
              {step === 2 && (
                <motion.div
                  key="working"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.25, ease }}
                  className="flex items-center gap-2 pl-8 text-[12px] text-muted-foreground"
                >
                  <span className="flex gap-1" aria-hidden="true">
                    {[0, 1, 2].map((d) => (
                      <motion.span
                        key={d}
                        className="size-1.5 rounded-full bg-primary"
                        animate={{ opacity: [0.25, 1, 0.25] }}
                        transition={{ duration: 1, repeat: Infinity, delay: d * 0.18 }}
                      />
                    ))}
                  </span>
                  Claude Code is working
                </motion.div>
              )}
              {published && (
                <motion.div
                  key="done"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.32, ease }}
                  className="flex items-start gap-2.5 pl-8"
                >
                  <div className="rounded-lg rounded-tl-sm border border-border bg-card px-3 py-2 text-[12px] leading-[17px] text-foreground">
                    Published <span className="font-medium tnum">v3</span>: revenue now split by region.
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
