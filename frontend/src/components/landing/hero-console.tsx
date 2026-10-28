"use client";

import { AnimatePresence, motion, useInView,  } from "motion/react";
import { useCalm } from "@/lib/motion";
import { Check, Pause, Play } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Status = "open" | "claimed" | "done";
type Line = { kind: "cmd" | "out" | "event"; text: string };
type PageState = { version: 1 | 2; status: Status | null; chart: boolean; reply: boolean };
type Step = { label: string; explain: string; lines: Line[]; page: PageState };

/**
 * One request, start to finish, exactly as an agent would do it with the paddock command line tool.
 * The commands and their answers are the real ones (see cli/README.md). Nothing here calls a server.
 */
const steps: Step[] = [
  {
    label: "Publish",
    explain: "Your agent runs one command. Paddock creates a private page and keeps it as version 1.",
    lines: [
      { kind: "cmd", text: 'paddock deploy ./q3-report -m "first draft"' },
      { kind: "out", text: 'Created "Q3 report" with version 1.' },
      { kind: "out", text: "  url: paddock.app/pages/q3-report" },
    ],
    page: { version: 1, status: null, chart: false, reply: false },
  },
  {
    label: "Ask",
    explain: "You comment and mention @agent. The request reaches your agent the moment it is made, with no polling.",
    lines: [
      { kind: "event", text: "comment.created  Maya: @agent add a revenue chart" },
      { kind: "event", text: "request.created  r_7f3a  status: open" },
    ],
    page: { version: 1, status: "open", chart: false, reply: false },
  },
  {
    label: "Claim",
    explain: "The agent claims the request, so two agents never do the same job. The claim lapses if it goes quiet.",
    lines: [
      { kind: "cmd", text: "paddock claim r_7f3a" },
      { kind: "out", text: "Claimed until 14:12 UTC." },
    ],
    page: { version: 1, status: "claimed", chart: false, reply: false },
  },
  {
    label: "Revise",
    explain: "It publishes a new version. Version 1 is untouched, so you can always go back.",
    lines: [
      { kind: "cmd", text: 'paddock deploy ./q3-report --page q3-report -m "revenue chart"' },
      { kind: "out", text: 'Published version 2 of "Q3 report".' },
    ],
    page: { version: 2, status: "claimed", chart: true, reply: false },
  },
  {
    label: "Reply",
    explain: "It answers in the thread and closes the request with the version that fixed it.",
    lines: [
      { kind: "cmd", text: 'paddock reply r_7f3a -m "Chart added" --done --version 2' },
      { kind: "out", text: "Done. Request completed with version 2." },
    ],
    page: { version: 2, status: "done", chart: true, reply: true },
  },
];

const TICK = 28; // milliseconds per frame
const OUT_GAP = 9; // frames between output lines
const HOLD = 60; // frames to rest after a step finishes

function timing(step: Step) {
  const cmdLen = step.lines[0].kind === "cmd" ? step.lines[0].text.length : 0;
  const rest = step.lines.length - 1;
  const applyAt = cmdLen + OUT_GAP * (rest + 1);
  return { cmdLen, applyAt, endAt: applyAt + HOLD };
}

function Terminal({ step, p }: { step: number; p: number }) {
  const rows: { key: string; line: Line; text: string; live: boolean }[] = [];
  steps.forEach((s, si) => {
    if (si > step) return;
    const { cmdLen } = timing(s);
    s.lines.forEach((line, li) => {
      let text = line.text;
      if (si === step) {
        if (li === 0) {
          if (line.kind === "cmd") text = line.text.slice(0, Math.min(p, cmdLen));
        } else if (p < cmdLen + OUT_GAP * li) return;
      }
      rows.push({ key: `${si}-${li}`, line, text, live: si === step && li === 0 && line.kind === "cmd" && p < cmdLen });
    });
  });

  return (
    <div
      aria-hidden="true"
      className="flex h-[292px] flex-col justify-end gap-1.5 overflow-hidden px-4 pb-4 pt-8 font-mono text-[12.5px] leading-[18px] [mask-image:linear-gradient(to_bottom,transparent,black_28%)]"
    >
      {rows.map(({ key, line, text, live }) => (
        <motion.p
          key={key}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className={cn(
            "break-words",
            line.kind === "cmd" && "text-ink-foreground",
            line.kind === "out" && "text-ink-muted",
            line.kind === "event" && "text-ink-accent",
          )}
        >
          {line.kind === "cmd" && <span className="mr-2 text-signal">$</span>}
          {line.kind === "event" && <span className="mr-2 text-ink-muted">event</span>}
          {text}
          {live && <span className="ml-0.5 inline-block h-[14px] w-[7px] translate-y-[2px] bg-ink-foreground [animation:blink_1s_steps(1)_infinite]" />}
        </motion.p>
      ))}
    </div>
  );
}

function StatusChip({ status }: { status: Status }) {
  const map = {
    open: { text: "Open", cls: "bg-signal text-signal-foreground" },
    claimed: { text: "Claimed by claude-code", cls: "bg-[#1e1b5e] text-[#f5f3ee]" },
    done: { text: "Done in v2", cls: "border border-[#0f1115] bg-transparent text-[#0f1115]" },
  }[status];
  return (
    <motion.span
      key={status}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold", map.cls)}
    >
      {status === "done" && <Check size={11} strokeWidth={3} />}
      {map.text}
    </motion.span>
  );
}

function PageMock({ page }: { page: PageState | null }) {
  const tiles = [
    ["Revenue", "$412k"],
    ["Growth", "+18%"],
    ["Churn", "2.1%"],
  ];
  return (
    <div aria-hidden="true" className="overflow-hidden rounded-xl border border-ink-line bg-[#f5f3ee] text-[#0f1115] shadow-[0_30px_80px_-20px_rgba(0,0,0,0.6)]">
      <div className="flex items-center gap-2 border-b border-[rgba(15,17,21,0.14)] bg-[#ece9e1] px-3 py-2">
        <span className="flex gap-1">
          <i className="size-2 rounded-full bg-[#0f1115]/25" />
          <i className="size-2 rounded-full bg-[#0f1115]/25" />
          <i className="size-2 rounded-full bg-[#0f1115]/25" />
        </span>
        <span className="min-w-0 flex-1 truncate rounded-md bg-white px-2.5 py-1 font-mono text-[10.5px] text-[#565a66]">
          paddock.app/pages/q3-report
        </span>
        <span className="flex items-center gap-1.5 font-mono text-[10px] font-semibold tracking-[0.08em] text-[#0f1115]">
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full rounded-full bg-signal [animation:pulse-ring_1.8s_ease-out_infinite]" />
            <span className="relative inline-flex size-2 rounded-full bg-signal" />
          </span>
          LIVE
        </span>
      </div>

      <div className="relative min-h-[292px] p-4">
        {!page ? (
          <div className="flex h-[260px] flex-col items-center justify-center gap-2 text-center">
            <span className="eyebrow text-[#565a66]">Waiting for the first publish</span>
            <span className="h-1 w-24 overflow-hidden rounded-full bg-[#0f1115]/10">
              <span className="block h-full w-1/2 rounded-full bg-[#3b33c9] [animation:marquee_1.4s_linear_infinite]" />
            </span>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="font-display text-[17px] font-bold tracking-[-0.02em]">
                Q3 report
              </motion.p>
              <AnimatePresence mode="popLayout">
                <motion.span
                  key={page.version}
                  initial={{ y: -8, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: 8, opacity: 0 }}
                  className="tnum rounded-full bg-[#e6e4fa] px-2 py-0.5 font-mono text-[10.5px] font-bold text-[#3b33c9]"
                >
                  v{page.version}
                </motion.span>
              </AnimatePresence>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2">
              {tiles.map(([k, v], i) => (
                <motion.div
                  key={k}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08 }}
                  className="rounded-lg bg-white p-2.5 shadow-[0_1px_2px_rgba(15,17,40,0.08)]"
                >
                  <p className="text-[10px] text-[#565a66]">{k}</p>
                  <p className="tnum font-display text-[16px] font-bold tracking-[-0.02em]">{v}</p>
                </motion.div>
              ))}
            </div>

            <div className="mt-3 h-[88px] rounded-lg border border-dashed border-[rgba(15,17,21,0.3)] bg-white/60 p-2">
              {page.chart ? (
                <svg viewBox="0 0 300 70" className="h-full w-full">
                  <motion.path
                    d="M0 58 C30 52 50 56 80 40 S130 44 160 28 S230 34 260 14 L300 8 L300 70 L0 70 Z"
                    fill="#e6e4fa"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.5, duration: 0.5 }}
                  />
                  <motion.path
                    d="M0 58 C30 52 50 56 80 40 S130 44 160 28 S230 34 260 14 L300 8"
                    fill="none"
                    stroke="#3b33c9"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ duration: 0.9 }}
                  />
                  <motion.circle cx="300" cy="8" r="4" fill="#ff6b4a" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.9 }} />
                </svg>
              ) : (
                <span className="flex h-full items-center justify-center font-mono text-[10.5px] text-[#565a66]">no chart yet</span>
              )}
            </div>

            {page.status && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-3 space-y-1.5 rounded-lg border border-[rgba(15,17,21,0.2)] bg-white p-2.5 shadow-[0_8px_24px_-8px_rgba(15,17,40,0.25)]"
              >
                <div className="flex items-start gap-2">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[#1e1b5e] text-[10px] font-bold text-[#f5f3ee]">M</span>
                  <p className="min-w-0 flex-1 text-[11.5px] leading-[16px]">
                    <span className="font-semibold text-[#3b33c9]">@agent</span> add a revenue chart
                  </p>
                  <StatusChip status={page.status} />
                </div>
                {page.reply && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="ml-7 rounded-md bg-[#ece9e1] px-2 py-1 text-[11px]">
                    Chart added in v2.
                  </motion.p>
                )}
              </motion.div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function HeroConsole() {
  const reduce = useCalm();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { margin: "-80px" });
  const [wantsPlay, setWantsPlay] = useState(true);
  const [step, setStep] = useState(0);
  const [p, setP] = useState(0);
  const [settled, setSettled] = useState(false);

  // People who prefer reduced motion get the finished story, and can step through it.
  useEffect(() => {
    if (reduce) {
      setWantsPlay(false);
      setStep(steps.length - 1);
      setP(99999);
      setSettled(true);
    }
  }, [reduce]);

  const playing = wantsPlay && inView && !settled;

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setP((v) => v + 1), TICK);
    return () => clearInterval(id);
  }, [playing]);

  useEffect(() => {
    if (!playing) return;
    if (p >= timing(steps[step]).endAt) {
      setStep((s) => (s + 1) % steps.length);
      setP(0);
    }
  }, [p, step, playing]);

  const jump = useCallback(
    (k: number) => {
      setSettled(false);
      setStep(k);
      setP(wantsPlay ? 0 : 99999);
      if (!wantsPlay) setSettled(true);
    },
    [wantsPlay],
  );

  const { applyAt } = timing(steps[step]);
  const applied = p >= applyAt;
  const page = applied ? steps[step].page : step > 0 ? steps[step - 1].page : null;

  function toggle() {
    if (wantsPlay) {
      setWantsPlay(false);
    } else {
      setSettled(false);
      setWantsPlay(true);
      if (p >= 99999) {
        setStep(0);
        setP(0);
      }
    }
  }

  return (
    <div ref={ref} id="loop">
      <div className="grid gap-4 lg:grid-cols-[1.15fr_1fr]">
        <div className="overflow-hidden rounded-xl border border-ink-line bg-ink-card shadow-[0_30px_80px_-20px_rgba(0,0,0,0.6)]">
          <div className="flex items-center gap-2 border-b border-ink-line px-3 py-2">
            <span className="flex gap-1" aria-hidden="true">
              <i className="size-2 rounded-full bg-ink-muted/40" />
              <i className="size-2 rounded-full bg-ink-muted/40" />
              <i className="size-2 rounded-full bg-ink-muted/40" />
            </span>
            <span className="eyebrow flex-1 text-ink-muted">your agent, in a terminal</span>
            <button
              type="button"
              onClick={toggle}
              aria-label={wantsPlay ? "Pause the demonstration" : "Play the demonstration"}
              className="flex h-7 items-center gap-1.5 rounded-md border border-ink-line px-2 text-[11px] font-medium text-ink-foreground transition-colors hover:bg-white/10"
            >
              {wantsPlay ? <Pause size={12} aria-hidden="true" /> : <Play size={12} aria-hidden="true" />}
              {wantsPlay ? "Pause" : "Play"}
            </button>
          </div>
          <Terminal step={step} p={p} />
        </div>
        <PageMock page={page} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.15fr_1fr]">
        <ol className="flex flex-wrap gap-2" aria-label="Steps of one request">
          {steps.map((s, i) => (
            <li key={s.label}>
              <button
                type="button"
                onClick={() => jump(i)}
                aria-current={i === step ? "step" : undefined}
                className={cn(
                  "eyebrow flex h-8 items-center gap-2 rounded-full border px-3 transition-colors",
                  i === step
                    ? "border-signal bg-signal text-signal-foreground"
                    : "border-ink-line text-ink-muted hover:bg-white/10 hover:text-ink-foreground",
                )}
              >
                <span aria-hidden="true">{String(i + 1).padStart(2, "0")}</span>
                {s.label}
              </button>
            </li>
          ))}
        </ol>
        <p className="min-h-[44px] text-[14px] leading-[22px] text-ink-muted">
          <span className="font-semibold text-ink-foreground">Step {step + 1} of {steps.length}. </span>
          {steps[step].explain}
        </p>
      </div>

      <div className="sr-only">
        <h2>What the animation shows</h2>
        <ol>
          {steps.map((s) => (
            <li key={s.label}>
              {s.label}: {s.explain} {s.lines.map((l) => l.text).join(" ")}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
