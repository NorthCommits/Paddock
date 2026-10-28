"use client";

import { AnimatePresence, motion, useMotionValueEvent, useScroll, useTransform } from "motion/react";
import { useRef, useState } from "react";
import { useCalm } from "@/lib/motion";
import { cn } from "@/lib/utils";

const steps = [
  { title: "Make a token", body: "One token per agent. You can revoke it at any time.", visual: "pdk_live_8f3a...c91e" },
  { title: "Your agent publishes", body: "A page appears in your workspace the moment the agent sends it.", visual: "Weekly report  /  v1  /  Published" },
  { title: "You leave a comment", body: "Comment on any line. Your agent receives it as a request.", visual: "\"Can the chart start at zero?\"" },
  { title: "The agent revises", body: "A new version is saved. The old one stays in the history.", visual: "Weekly report  /  v2  /  Done" },
];

/** A pinned story. The page stays put while the scroll moves through four steps. */
export function ScrollStory() {
  const calm = useCalm();
  const ref = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const fill = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);
  useMotionValueEvent(scrollYProgress, "change", (v) => setStep(Math.min(steps.length - 1, Math.floor(v * steps.length))));

  if (calm) {
    return (
      <section id="story" className="on-band bg-ink text-ink-foreground" aria-labelledby="story-title">
        <div className="mx-auto max-w-[1200px] px-6 py-24">
          <h2 id="story-title" className="font-display text-[32px] font-bold tracking-[-0.03em] md:text-[44px]">Four steps, no setup.</h2>
          <ol className="mt-8 space-y-4">
            {steps.map((s, i) => (
              <li key={s.title} className="rounded-xl border border-ink-line bg-ink-card p-5">
                <p className="eyebrow text-ink-accent">Step {i + 1}</p>
                <p className="mt-1 text-[18px] font-semibold">{s.title}</p>
                <p className="mt-1 text-ink-muted">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>
    );
  }

  return (
    <section id="story" ref={ref} className="on-band relative h-[320vh] bg-ink text-ink-foreground" aria-labelledby="story-title">
      <div className="sticky top-14 flex h-[calc(100dvh-3.5rem)] items-center overflow-hidden">
        <div className="mx-auto grid w-full max-w-[1200px] gap-10 px-6 md:grid-cols-2 md:items-center">
          <div>
            <p className="eyebrow text-ink-accent">Scroll to follow one request</p>
            <h2 id="story-title" className="mt-2 font-display text-[32px] font-bold leading-[1.05] tracking-[-0.03em] md:text-[48px]">
              Four steps, <span className="serif-accent text-signal">no setup.</span>
            </h2>
            <ol className="mt-8 space-y-3">
              {steps.map((s, i) => (
                <li
                  key={s.title}
                  aria-current={i === step ? "step" : undefined}
                  className={cn("flex gap-3 transition-colors duration-300", i === step ? "text-ink-foreground" : "text-ink-muted")}
                >
                  <span className={cn("eyebrow mt-1 w-6", i === step && "text-signal")}>{String(i + 1).padStart(2, "0")}</span>
                  <span>
                    <span className="block text-[17px] font-semibold">{s.title}</span>
                    <span className="block text-[14px] leading-[22px]">{s.body}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>

          <div className="relative">
            <div className="rounded-2xl border border-ink-line bg-ink-card p-6">
              <div className="h-1.5 overflow-hidden rounded-full bg-ink-line" aria-hidden="true">
                <motion.div className="h-full bg-signal" style={{ width: fill }} />
              </div>
              <div className="mt-8 flex min-h-[160px] items-center" aria-hidden="true">
                <AnimatePresence mode="wait">
                  <motion.p
                    key={step}
                    initial={{ opacity: 0, y: 24, filter: "blur(6px)" }}
                    animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                    exit={{ opacity: 0, y: -24 }}
                    transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
                    className="font-mono text-[18px] leading-[28px] text-ink-accent md:text-[22px]"
                  >
                    {steps[step].visual}
                  </motion.p>
                </AnimatePresence>
              </div>
              <p className="sr-only" aria-live="polite">Step {step + 1} of {steps.length}: {steps[step].title}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
