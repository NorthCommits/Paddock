"use client";

import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "motion/react";
import { RotateCcw, Send } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Flags = { region: boolean; trend: boolean; peak: boolean };
type Msg = { id: number; who: "you" | "agent"; text: string };

const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
const base = [38, 52, 44, 66, 58, 78];
const other = [14, 20, 28, 22, 34, 30];
const H = 108;
const K = 0.85;
const ease = [0.2, 0, 0, 1] as const;

const suggestions = [
  { label: "Split by region", text: "split revenue by region", flag: "region" as const, reply: "revenue is now split by region" },
  { label: "Add a trend line", text: "add a trend line", flag: "trend" as const, reply: "added a trend line" },
  { label: "Highlight the peak", text: "highlight the best month", flag: "peak" as const, reply: "highlighted the best month" },
];

function interpret(text: string) {
  const t = text.toLowerCase();
  if (/(region|split|break)/.test(t)) return suggestions[0];
  if (/(trend|line|growth)/.test(t)) return suggestions[1];
  if (/(peak|best|highlight|top|max)/.test(t)) return suggestions[2];
  return null;
}

function Chart({ flags }: { flags: Flags }) {
  const w = 300;
  const slot = w / months.length;
  const barW = 28;
  const top = base.map((b, i) => b + (flags.region ? other[i] : 0));
  const peak = top.indexOf(Math.max(...top));
  const pts = base.map((b, i) => [slot * i + slot / 2, H - (b + (flags.region ? other[i] : 0)) * K] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${H + 18}`} className="w-full" aria-hidden="true">
      <line x1="0" x2={w} y1={H} y2={H} stroke="var(--border)" />
      {base.map((b, i) => {
        const x = slot * i + (slot - barW) / 2;
        const hb = b * K;
        const ho = flags.region ? other[i] * K : 0;
        return (
          <g key={i}>
            <motion.rect
              x={x}
              width={barW}
              rx={3}
              initial={false}
              animate={{ y: H - hb, height: hb }}
              fill={flags.peak && i === peak ? "var(--primary)" : "var(--primary)"}
              opacity={flags.peak && i !== peak ? 0.35 : 1}
              transition={{ duration: 0.6, delay: i * 0.04, ease }}
            />
            <motion.rect
              x={x}
              width={barW}
              rx={3}
              initial={false}
              animate={{ y: H - hb - ho, height: ho }}
              fill="var(--primary)"
              opacity={flags.peak && i !== peak ? 0.15 : 0.3}
              transition={{ duration: 0.6, delay: 0.15 + i * 0.04, ease }}
            />
            <text x={x + barW / 2} y={H + 13} textAnchor="middle" fontSize="6.5" fill="var(--subtle)" fontFamily="ui-monospace, monospace">
              {months[i]}
            </text>
          </g>
        );
      })}
      <motion.path
        d={line}
        fill="none"
        stroke="var(--foreground)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={false}
        animate={{ pathLength: flags.trend ? 1 : 0, opacity: flags.trend ? 1 : 0 }}
        transition={{ duration: 0.8, ease }}
      />
      {flags.peak && (
        <motion.g initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <text
            x={slot * peak + slot / 2}
            y={H - top[peak] * K - 6}
            textAnchor="middle"
            fontSize="7.5"
            fontWeight="600"
            fill="var(--foreground)"
          >
            Best month
          </text>
        </motion.g>
      )}
    </svg>
  );
}

/** An interactive, original illustration of the Paddock loop. Nothing here calls a server or a model. */
export function HeroDemo() {
  const reduce = useReducedMotion();
  const idRef = useRef(2);
  const [versions, setVersions] = useState<Flags[]>([{ region: false, trend: false, peak: false }]);
  const [current, setCurrent] = useState(0);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [touched, setTouched] = useState(false);

  const flags = versions[current];
  const latest = versions.length - 1;
  const full = versions.length >= 6;

  function send(raw: string) {
    const value = raw.trim();
    if (!value || busy) return;
    setTouched(true);
    const you: Msg = { id: idRef.current++, who: "you", text: value };
    setMsgs((m) => [...m, you].slice(-4));
    setText("");
    const hit = interpret(value);
    setBusy(true);
    setTimeout(
      () => {
        if (hit && !versions[latest][hit.flag] && !full) {
          const next = [...versions, { ...versions[latest], [hit.flag]: true }];
          setVersions(next);
          setCurrent(next.length - 1);
          setMsgs((m) => [...m, { id: idRef.current++, who: "agent" as const, text: `Published v${next.length}: ${hit.reply}.` }].slice(-4));
        } else {
          const reply = hit
            ? full
              ? "That is enough versions for the demo. Reset to start over."
              : "Already done in the latest version."
            : "This demo understands a few requests. Try one of the suggestions. Your real agent can do much more.";
          setMsgs((m) => [...m, { id: idRef.current++, who: "agent" as const, text: reply }].slice(-4));
        }
        setBusy(false);
      },
      reduce ? 200 : 1300,
    );
  }

  function reset() {
    setVersions([{ region: false, trend: false, peak: false }]);
    setCurrent(0);
    setMsgs([]);
    setBusy(false);
    setTouched(false);
    setText("");
  }

  return (
    <div className="w-full max-w-[540px]">
      <div className="rounded-xl border border-border bg-card shadow-float">
        <div className="flex items-center gap-3 border-b border-border px-4 py-2.5">
          <div className="flex gap-1.5" aria-hidden="true">
            <span className="size-2.5 rounded-full bg-border" />
            <span className="size-2.5 rounded-full bg-border" />
            <span className="size-2.5 rounded-full bg-border" />
          </div>
          <div className="flex-1 truncate rounded-md bg-muted px-3 py-1 text-center font-mono text-[11px] text-muted-foreground">
            paddock / monthly-revenue
          </div>
          <button
            onClick={reset}
            aria-label="Reset the demo"
            className="flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground"
          >
            <RotateCcw size={13} />
          </button>
        </div>

        <div className="p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[15px] font-semibold text-foreground">Monthly revenue</p>
              <p className="text-[12px] text-muted-foreground">Published by your agent</p>
            </div>
            <LayoutGroup>
              <div role="tablist" aria-label="Versions" className="flex gap-0.5 rounded-md bg-muted p-0.5">
                {versions.map((_, i) => (
                  <motion.button
                    key={i}
                    role="tab"
                    aria-selected={i === current}
                    layout
                    initial={i > 0 ? { opacity: 0, scale: 0.8 } : false}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3, ease }}
                    onClick={() => setCurrent(i)}
                    className={cn(
                      "tnum relative rounded-[5px] px-2.5 py-1 text-[12px] font-medium transition-colors duration-[120ms]",
                      i === current ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {i === current && (
                      <motion.span
                        layoutId="hero-ver"
                        className="absolute inset-0 rounded-[5px] bg-card shadow-sm"
                        transition={{ type: "spring", stiffness: 500, damping: 38 }}
                      />
                    )}
                    <span className="relative">v{i + 1}</span>
                  </motion.button>
                ))}
              </div>
            </LayoutGroup>
          </div>

          <div className="mt-4">
            <Chart flags={flags} />
            <div className="mt-1 flex h-4 items-center gap-3 text-[11px] text-muted-foreground">
              {flags.region && (
                <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-1.5">
                  <span className="size-2 rounded-sm bg-primary" /> North
                  <span className="ml-2 size-2 rounded-sm bg-primary/30" /> South
                </motion.span>
              )}
              {current !== latest && <span className="ml-auto">Viewing an earlier version</span>}
            </div>
          </div>

          <div className="mt-3 min-h-[118px] space-y-2" aria-live="polite">
            <AnimatePresence initial={false}>
              {msgs.map((m) => (
                <motion.div
                  key={m.id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3, ease }}
                  className={cn("flex items-start gap-2.5", m.who === "agent" && "pl-8")}
                >
                  {m.who === "you" && (
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[10px] font-semibold text-primary">
                      You
                    </span>
                  )}
                  <div
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-[12px] leading-[17px] text-foreground",
                      m.who === "you" ? "rounded-tl-sm bg-muted" : "rounded-tl-sm border border-border bg-card",
                    )}
                  >
                    {m.who === "you" && <span className="font-medium text-primary">@agent </span>}
                    {m.text}
                  </div>
                </motion.div>
              ))}
              {busy && (
                <motion.div
                  key="busy"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
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
                  Your agent is working
                </motion.div>
              )}
            </AnimatePresence>
            {msgs.length === 0 && !busy && (
              <p className="text-[12px] text-muted-foreground">
                Try it. Comment on this page and mention your agent. A new version appears.
              </p>
            )}
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {suggestions.map((s, i) => (
              <button
                key={s.label}
                disabled={busy}
                onClick={() => send(s.text)}
                className={cn(
                  "rounded-full border border-border bg-card px-2.5 py-1 text-[12px] text-foreground transition-[background-color,transform] duration-[120ms] hover:bg-muted active:scale-[0.97] disabled:opacity-50",
                  !touched && i === 0 && "animate-pulse border-primary text-primary",
                )}
              >
                {s.label}
              </button>
            ))}
          </div>

          <form
            className="mt-2.5 flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 transition-[border-color,box-shadow] duration-[120ms] focus-within:border-primary focus-within:ring-[3px] focus-within:ring-primary/25"
            onSubmit={(e) => {
              e.preventDefault();
              send(text);
            }}
          >
            <label htmlFor="hero-comment" className="sr-only">
              Comment and mention your agent
            </label>
            <span className="text-[13px] font-medium text-primary">@agent</span>
            <input
              id="hero-comment"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="ask for a change"
              className="min-w-0 flex-1 bg-transparent text-[13px] text-foreground outline-none placeholder:text-subtle"
              autoComplete="off"
            />
            <button
              type="submit"
              aria-label="Send comment"
              disabled={busy || !text.trim()}
              className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground transition-opacity duration-[120ms] disabled:opacity-40"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      </div>
      <p className="mt-3 text-center text-[12px] text-muted-foreground">
        A simulation. In Paddock your own agent makes the change.
      </p>
    </div>
  );
}
