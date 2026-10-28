"use client";

import { AnimatePresence, motion,  } from "motion/react";
import { useCalm } from "@/lib/motion";
import { History, RotateCcw, Undo2 } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Reveal } from "./motion-bits";

type Spec = {
  big: boolean;
  chart: boolean;
  region: boolean;
  summary: boolean;
  indigo: boolean;
};
type Version = { n: number; by: "agent" | "person"; who: string; msg: string; when: string; spec: Spec };

const base: Spec = { big: false, chart: false, region: false, summary: false, indigo: false };

const seed: Version[] = [
  { n: 1, by: "agent", who: "claude-code", msg: "First draft", when: "09:02", spec: base },
  { n: 2, by: "agent", who: "claude-code", msg: "Add a revenue chart", when: "09:14", spec: { ...base, chart: true } },
  { n: 3, by: "agent", who: "claude-code", msg: "Bigger heading, as Maya asked", when: "09:31", spec: { ...base, chart: true, big: true } },
  { n: 4, by: "agent", who: "codex", msg: "Split revenue by region", when: "10:05", spec: { ...base, chart: true, big: true, region: true } },
  { n: 5, by: "agent", who: "codex", msg: "Try an indigo theme", when: "10:40", spec: { ...base, chart: true, big: true, region: true, indigo: true } },
  { n: 6, by: "agent", who: "claude-code", msg: "Add a summary at the top", when: "11:12", spec: { ...base, chart: true, big: true, region: true, indigo: true, summary: true } },
];

function MiniPage({ spec, n }: { spec: Spec; n: number }) {
  const reduce = useCalm();
  const t = reduce ? { duration: 0 } : { type: "spring" as const, stiffness: 300, damping: 30 };
  return (
    <div aria-hidden="true" className="overflow-hidden rounded-xl border border-ink-line bg-[#f5f3ee] text-[#0f1115] shadow-[0_30px_80px_-20px_rgba(0,0,0,0.6)]">
      <div className="flex items-center gap-2 border-b border-[rgba(15,17,21,0.14)] bg-[#ece9e1] px-3 py-2">
        <span className="flex gap-1">
          <i className="size-2 rounded-full bg-[#0f1115]/25" />
          <i className="size-2 rounded-full bg-[#0f1115]/25" />
          <i className="size-2 rounded-full bg-[#0f1115]/25" />
        </span>
        <span className="min-w-0 flex-1 truncate rounded-md bg-white px-2.5 py-1 font-mono text-[10.5px] text-[#565a66]">paddock.app/pages/q3-report</span>
        <span className="tnum rounded-full bg-[#0f1115] px-2 py-0.5 font-mono text-[10.5px] font-bold text-[#f5f3ee]">v{n}</span>
      </div>

      <motion.div layout transition={t} className="min-h-[330px] p-4">
        <motion.div layout transition={t} className={cn("rounded-lg px-3 py-2", spec.indigo ? "bg-[#1e1b5e] text-[#f5f3ee]" : "bg-transparent")}>
          <motion.p
            layout
            animate={{ fontSize: spec.big ? 30 : 17 }}
            transition={t}
            className="font-display font-bold leading-[1.05] tracking-[-0.03em]"
          >
            Q3 report
          </motion.p>
        </motion.div>

        <AnimatePresence initial={false}>
          {spec.summary && (
            <motion.p
              key="sum"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-2 overflow-hidden rounded-md bg-white px-3 py-2 text-[11.5px] leading-[16px] text-[#565a66]"
            >
              <span className="font-semibold text-[#0f1115]">Summary.</span> Revenue is up 18% on the quarter, led by the north region. Churn is flat.
            </motion.p>
          )}
        </AnimatePresence>

        <div className="mt-3 grid grid-cols-3 gap-2">
          {[
            ["Revenue", "$412k"],
            ["Growth", "+18%"],
            ["Churn", "2.1%"],
          ].map(([k, v]) => (
            <div key={k} className="rounded-lg bg-white p-2.5 shadow-[0_1px_2px_rgba(15,17,40,0.08)]">
              <p className="text-[10px] text-[#565a66]">{k}</p>
              <p className="tnum font-display text-[15px] font-bold tracking-[-0.02em]">{v}</p>
            </div>
          ))}
        </div>

        <AnimatePresence initial={false}>
          {spec.chart && (
            <motion.div
              key="chart"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-3 overflow-hidden rounded-lg bg-white p-2"
            >
              <svg viewBox="0 0 300 70" className="h-[84px] w-full">
                <path d="M0 58 C30 52 50 56 80 40 S130 44 160 28 S230 34 260 14 L300 8 L300 70 L0 70 Z" fill="#e6e4fa" />
                <path d="M0 58 C30 52 50 56 80 40 S130 44 160 28 S230 34 260 14 L300 8" fill="none" stroke="#3b33c9" strokeWidth="2.5" strokeLinecap="round" />
                {spec.region && (
                  <path d="M0 64 C30 62 50 63 80 54 S130 56 160 46 S230 50 260 36 L300 32" fill="none" stroke="#0f1115" strokeWidth="2" strokeDasharray="5 4" strokeLinecap="round" />
                )}
              </svg>
              {spec.region && (
                <p className="mt-1 flex gap-3 font-mono text-[10px] text-[#565a66]">
                  <span><b className="text-[#3b33c9]">solid</b> north</span>
                  <span><b className="text-[#0f1115]">dashed</b> south</span>
                </p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

/**
 * Scrub through the history of a page. The slider is a real range input, so it works with a mouse,
 * a finger and the arrow keys. Restoring an old version copies it forward as a new one: nothing is lost.
 */
export function VersionTimeline() {
  const [versions, setVersions] = useState<Version[]>(seed);
  const [at, setAt] = useState(seed.length);
  const total = versions.length;
  const v = versions[at - 1];
  const pct = total > 1 ? ((at - 1) / (total - 1)) * 100 : 0;
  const isLatest = at === total;
  const restored = versions.length > seed.length;

  function restore() {
    const next: Version = {
      n: total + 1,
      by: "person",
      who: "you",
      msg: `Restored version ${v.n}`,
      when: "now",
      spec: v.spec,
    };
    setVersions((cur) => [...cur, next]);
    setAt(total + 1);
  }

  return (
    <section id="history" aria-labelledby="history-title" className="relative overflow-hidden bg-ink py-24 text-ink-foreground md:py-32">
      <div className="mx-auto max-w-[1200px] px-6">
        <Reveal>
          <p className="eyebrow text-ink-muted">[03] History</p>
          <h2 id="history-title" className="mt-3 max-w-[16ch] text-[40px] font-bold leading-[1.02] tracking-[-0.04em] md:text-[72px]">
            Scrub through <span className="serif-accent text-signal">every version.</span>
          </h2>
          <p className="mt-5 max-w-[40rem] text-[17px] leading-[26px] text-ink-muted">
            Every publish is kept, with who made it and why. Drag the playhead, or use the arrow keys, and the page
            changes with it. Restoring never deletes anything. It copies the old version forward as a new one.
          </p>
        </Reveal>

        <div className="mt-12 grid items-start gap-8 lg:grid-cols-[1fr_1.05fr]">
          <div className="order-2 lg:order-1">
            <div className="rounded-xl border border-ink-line bg-ink-card p-5 md:p-6">
              <div className="flex items-center justify-between">
                <h3 className="eyebrow flex items-center gap-2 text-ink-muted"><History size={14} aria-hidden="true" /> Version history</h3>
                <span className="tnum font-mono text-[12px] text-ink-muted">{total} versions</span>
              </div>

              <div className="relative mt-8 h-14 select-none">
                <input
                  type="range"
                  min={1}
                  max={total}
                  step={1}
                  value={at}
                  onChange={(e) => setAt(Number(e.target.value))}
                  aria-label="Version of the page"
                  aria-valuetext={`Version ${v.n} of ${total}. ${v.msg}, by ${v.who}`}
                  className="peer absolute inset-0 z-10 h-full w-full cursor-grab opacity-0 active:cursor-grabbing"
                />
                <div aria-hidden="true" className="absolute inset-x-3 top-[26px] h-[3px] rounded-full bg-ink-line" />
                <motion.div aria-hidden="true" className="absolute left-3 top-[26px] h-[3px] rounded-full bg-signal" animate={{ width: `calc((100% - 24px) * ${pct / 100})` }} transition={{ duration: 0.2 }} />
                {versions.map((x, i) => (
                  <span
                    key={x.n}
                    aria-hidden="true"
                    className={cn(
                      "absolute top-[21px] size-[13px] -translate-x-1/2 rounded-full border-2 bg-ink-card",
                      x.by === "person" ? "rotate-45 rounded-[3px] border-ink-accent" : i < at ? "border-signal" : "border-ink-muted",
                    )}
                    style={{ left: `calc(12px + (100% - 24px) * ${total > 1 ? i / (total - 1) : 0})` }}
                  />
                ))}
                {versions.map((x, i) => (
                  <span
                    key={`l${x.n}`}
                    aria-hidden="true"
                    className={cn("tnum absolute top-[42px] -translate-x-1/2 font-mono text-[10.5px]", i === at - 1 ? "text-ink-foreground" : "text-ink-muted")}
                    style={{ left: `calc(12px + (100% - 24px) * ${total > 1 ? i / (total - 1) : 0})` }}
                  >
                    v{x.n}
                  </span>
                ))}
                <motion.div
                  aria-hidden="true"
                  className="pointer-events-none absolute top-[12px] size-[30px] -translate-x-1/2 rounded-full border-[3px] border-signal bg-ink shadow-[0_0_0_6px_rgba(255,107,74,0.18)] peer-focus-visible:ring-4 peer-focus-visible:ring-ink-foreground"
                  animate={{ left: `calc(12px + (100% - 24px) * ${pct / 100})` }}
                  transition={{ type: "spring", stiffness: 500, damping: 38 }}
                />
              </div>

              <AnimatePresence mode="wait">
                <motion.div
                  key={v.n}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="mt-6 rounded-lg border border-ink-line bg-ink p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-display text-[18px] font-bold tracking-[-0.02em]">Version {v.n}</p>
                    <span className="eyebrow rounded-full border border-ink-line px-2 py-0.5 text-ink-muted">{isLatest ? "current" : "older"}</span>
                  </div>
                  <p className="mt-1 text-[15px] leading-[22px] text-ink-foreground">{v.msg}</p>
                  <p className="mt-1 font-mono text-[12px] text-ink-muted">
                    {v.by === "agent" ? "agent" : "person"} · {v.who} · {v.when}
                  </p>
                </motion.div>
              </AnimatePresence>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                {isLatest ? (
                  <p className="text-[13px] leading-[19px] text-ink-muted">Drag the playhead back to an older version to restore it.</p>
                ) : (
                  <button
                    type="button"
                    onClick={restore}
                    className="flex h-9 items-center gap-2 rounded-md bg-signal px-3 text-[13px] font-semibold text-signal-foreground transition-colors hover:bg-signal-hover"
                  >
                    <Undo2 size={15} aria-hidden="true" /> Restore version {v.n}
                  </button>
                )}
                {restored && (
                  <button
                    type="button"
                    onClick={() => {
                      setVersions(seed);
                      setAt(seed.length);
                    }}
                    className="flex h-9 items-center gap-2 rounded-md border border-ink-line px-3 text-[13px] font-medium text-ink-foreground transition-colors hover:bg-white/10"
                  >
                    <RotateCcw size={14} aria-hidden="true" /> Start over
                  </button>
                )}
              </div>
              <p role="status" className="mt-3 min-h-[20px] text-[12.5px] leading-[18px] text-ink-muted">
                {restored && isLatest ? `Done. Version ${v.n} is a copy, and versions 1 to ${total - 1} are all still here.` : ""}
              </p>
              <p className="mt-2 flex items-center gap-4 font-mono text-[11px] text-ink-muted">
                <span className="flex items-center gap-1.5"><span aria-hidden="true" className="size-2.5 rounded-full border-2 border-signal" /> by an agent</span>
                <span className="flex items-center gap-1.5"><span aria-hidden="true" className="size-2.5 rotate-45 rounded-[2px] border-2 border-ink-accent" /> by a person</span>
              </p>
            </div>
          </div>

          <div className="order-1 lg:order-2 lg:sticky lg:top-24">
            <MiniPage spec={v.spec} n={v.n} />
          </div>
        </div>
      </div>
    </section>
  );
}
