"use client";

import { motion } from "motion/react";
import { Reveal } from "./motion-bits";

const widths = [92, 100, 84, 96, 70, 100, 88, 94, 62, 100, 90, 76, 98, 82, 58];

export function Why() {
  return (
    <section aria-labelledby="why" className="mx-auto max-w-[1200px] px-6 py-24">
      <Reveal>
        <p className="eyebrow text-primary">Why Paddock</p>
        <h2 id="why" className="mt-2 max-w-[20ch] text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
          Agents write faster than anyone can read.
        </h2>
        <p className="mt-4 max-w-[40rem] text-[17px] leading-[26px] text-muted-foreground">
          A long chat reply is easy to produce and tiring to use. Ask your agent for a page instead, with a chart, a
          layout, or a small app, and keep every version.
        </p>
      </Reveal>

      <div className="mt-12 grid gap-4 md:grid-cols-2">
        <Reveal>
          <div className="h-full rounded-xl border border-dashed border-border bg-muted p-6">
            <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-subtle">A wall of text</p>
            <div className="mt-5 space-y-2.5" aria-hidden="true">
              {widths.map((w, i) => (
                <motion.div
                  key={i}
                  className="h-2 rounded-full bg-border"
                  style={{ width: `${w}%` }}
                  initial={{ scaleX: 0, originX: 0 }}
                  whileInView={{ scaleX: 1 }}
                  viewport={{ once: true, margin: "-40px" }}
                  transition={{ delay: i * 0.04, duration: 0.5, ease: [0.2, 0, 0, 1] }}
                />
              ))}
            </div>
            <p className="mt-6 text-[13px] text-muted-foreground">Hard to scan. Hard to comment on. Gone when the chat scrolls.</p>
          </div>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="h-full rounded-xl border border-border bg-card p-6 shadow-card">
            <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-primary">A Paddock page</p>
            <div className="mt-5 grid grid-cols-3 gap-2" aria-hidden="true">
              {[
                ["Revenue", "$412k"],
                ["Growth", "+18%"],
                ["Churn", "2.1%"],
              ].map(([k, v], i) => (
                <motion.div
                  key={k}
                  className="rounded-lg bg-primary-soft p-3"
                  initial={{ opacity: 0, y: 12 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.2 + i * 0.1, duration: 0.45, ease: [0.2, 0, 0, 1] }}
                >
                  <p className="text-[11px] text-muted-foreground">{k}</p>
                  <p className="tnum mt-0.5 text-[20px] font-semibold tracking-[-0.02em] text-foreground">{v}</p>
                </motion.div>
              ))}
            </div>
            <svg viewBox="0 0 300 70" className="mt-4 w-full" aria-hidden="true">
              <motion.path
                d="M0 58 C30 52 50 56 80 40 S130 44 160 28 S230 34 260 14 L300 8"
                fill="none"
                stroke="var(--primary)"
                strokeWidth="2.5"
                strokeLinecap="round"
                initial={{ pathLength: 0 }}
                whileInView={{ pathLength: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.5, duration: 1.2, ease: [0.2, 0, 0, 1] }}
              />
            </svg>
            <p className="mt-3 text-[13px] text-muted-foreground">One glance. Comment on any line. Every version kept.</p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
