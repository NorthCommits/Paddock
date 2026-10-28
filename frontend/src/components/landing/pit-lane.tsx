"use client";

import { AnimatePresence, LayoutGroup, motion, useInView,  } from "motion/react";
import { useCalm } from "@/lib/motion";
import { ArrowRight, Pause, Play, Plus } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Reveal } from "./motion-bits";

const stages = [
  { id: 0, name: "Open", hint: "Waiting for an agent" },
  { id: 1, name: "Claimed", hint: "One agent holds it" },
  { id: 2, name: "Publishing", hint: "A new version is on the way" },
  { id: 3, name: "Done", hint: "Closed with a version" },
] as const;

const asks = [
  "shorten the intro",
  "add a revenue chart",
  "fix the table on mobile",
  "translate to Hindi",
  "make the heading bigger",
  "add a summary at the top",
  "swap the colours",
  "split sales by region",
];

const agentNames = ["claude-code", "codex", "cursor"];

type Req = { id: number; ask: string; stage: 0 | 1 | 2 | 3; agent: string | null; version: number | null };

/** Which agent is doing what, as light and words. Never colour alone. */
function AgentLight({ name, job }: { name: string; job: Req | null }) {
  const state = !job ? "idle" : job.stage === 1 ? "claimed" : "working";
  return (
    <li className="flex items-center gap-3 rounded-lg border border-ink-line bg-ink/40 px-3 py-2.5">
      <span className="relative flex size-3 shrink-0 items-center justify-center" aria-hidden="true">
        {state === "working" && <span className="absolute inline-flex size-full rounded-full bg-signal [animation:pulse-ring_1.4s_ease-out_infinite]" />}
        <span
          className={cn(
            "relative inline-flex size-3 rounded-full",
            state === "idle" && "border-2 border-ink-muted",
            state === "claimed" && "border-2 border-signal",
            state === "working" && "bg-signal",
          )}
        />
      </span>
      <span className="font-mono text-[12.5px] text-ink-foreground">{name}</span>
      <span className="eyebrow ml-auto text-ink-muted">
        {state === "idle" ? "idle" : state === "claimed" ? `holds #${job!.id}` : `building #${job!.id}`}
      </span>
    </li>
  );
}

/**
 * The life of a request, drawn as a pit lane. Cars (requests) enter at Open, an agent claims one,
 * it moves through Publishing, and the flag drops at Done. You can add your own request and
 * move things along. It stops by itself when scrolled out of view, and has a pause button.
 */
export function PitLane() {
  const reduce = useCalm();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { margin: "-60px" });
  const nextId = useRef(4);
  const [auto, setAuto] = useState(true);
  const [announce, setAnnounce] = useState("");
  const [reqs, setReqs] = useState<Req[]>([
    { id: 1, ask: asks[0], stage: 3, agent: "claude-code", version: 2 },
    { id: 2, ask: asks[1], stage: 2, agent: "codex", version: null },
    { id: 3, ask: asks[2], stage: 1, agent: "cursor", version: null },
  ]);

  const spawn = useCallback((text?: string) => {
    setReqs((cur) => {
      if (cur.filter((r) => r.stage === 0).length >= 3) return cur;
      const id = nextId.current++;
      const ask = text ?? asks[id % asks.length];
      const added: Req = { id, ask, stage: 0, agent: null, version: null };
      return [...cur, added].slice(-9);
    });
  }, []);

  const advance = useCallback(() => {
    setReqs((cur) => {
      const busy = new Set(cur.filter((r) => r.stage === 1 || r.stage === 2).map((r) => r.agent));
      const free = agentNames.filter((a) => !busy.has(a));
      // Move the request furthest along first, so the lane keeps flowing.
      const order = [2, 1, 0];
      for (const stage of order) {
        const r = cur.find((x) => x.stage === stage);
        if (!r) continue;
        if (stage === 0 && free.length === 0) continue;
        return cur.map((x) => {
          if (x.id !== r.id) return x;
          if (stage === 0) return { ...x, stage: 1, agent: free[0] };
          if (stage === 1) return { ...x, stage: 2 };
          return { ...x, stage: 3, version: 2 + (x.id % 5) };
        });
      }
      return cur;
    });
  }, []);

  useEffect(() => {
    if (!auto || !inView || reduce) return;
    const id = setInterval(() => {
      advance();
      if (Math.random() < 0.55) spawn();
    }, 1900);
    return () => clearInterval(id);
  }, [auto, inView, reduce, advance, spawn]);

  const counts = stages.map((s) => reqs.filter((r) => r.stage === s.id).length);
  const jobOf = (name: string) => reqs.find((r) => r.agent === name && (r.stage === 1 || r.stage === 2)) ?? null;

  return (
    <section id="lane" aria-labelledby="lane-title" className="on-band relative overflow-hidden bg-band py-24 text-band-foreground md:py-32">
      <div aria-hidden="true" className="grain pointer-events-none absolute inset-0" />
      <div className="relative mx-auto max-w-[1200px] px-6">
        <Reveal>
          <p className="eyebrow text-band-muted">[02] The pit lane</p>
          <h2 id="lane-title" className="mt-3 max-w-[16ch] text-[40px] font-bold leading-[1.02] tracking-[-0.04em] md:text-[72px]">
            Every request gets <span className="serif-accent text-signal">a lane.</span>
          </h2>
          <p className="mt-5 max-w-[40rem] text-[17px] leading-[26px] text-band-muted">
            Ask in a comment and the request enters the lane. An agent claims it, publishes a new version and closes it.
            Press the buttons to add your own, or leave it running and watch the lights.
          </p>
        </Reveal>

        <div ref={ref} className="mt-12 grid gap-4 lg:grid-cols-[1fr_300px]">
          <div className="rounded-xl border border-white/15 bg-ink p-4 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.6)] md:p-5">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  spawn("shorten the intro");
                  setAnnounce("A request was added to the Open lane.");
                }}
                className="flex h-9 items-center gap-2 rounded-md bg-signal px-3 text-[13px] font-semibold text-signal-foreground transition-colors hover:bg-signal-hover"
              >
                <Plus size={15} aria-hidden="true" /> Mention @agent
              </button>
              <button
                type="button"
                onClick={() => {
                  advance();
                  setAnnounce("The lane moved forward one step.");
                }}
                className="flex h-9 items-center gap-2 rounded-md border border-ink-line px-3 text-[13px] font-medium text-ink-foreground transition-colors hover:bg-white/10"
              >
                Move things along <ArrowRight size={15} aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => setAuto((a) => !a)}
                disabled={reduce === true}
                className="ml-auto flex h-9 items-center gap-2 rounded-md border border-ink-line px-3 text-[13px] font-medium text-ink-foreground transition-colors hover:bg-white/10 disabled:opacity-50"
              >
                {auto && !reduce ? <Pause size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
                {auto && !reduce ? "Pause" : "Play"}
              </button>
            </div>

            <LayoutGroup>
              <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                {stages.map((s, i) => (
                  <div key={s.id} className="min-w-0">
                    <div className="flex items-baseline justify-between border-b-2 border-ink-line pb-2">
                      <span className="eyebrow text-ink-foreground">
                        <span className="text-signal">{String(i + 1).padStart(2, "0")}</span> {s.name}
                      </span>
                      <span className="tnum font-mono text-[18px] font-bold text-ink-foreground">{counts[i]}</span>
                    </div>
                    <p className="mt-1.5 text-[11.5px] leading-[15px] text-ink-muted">{s.hint}</p>
                    <ul className="mt-3 flex min-h-[210px] flex-col gap-2">
                      <AnimatePresence initial={false}>
                        {reqs
                          .filter((r) => r.stage === s.id)
                          .map((r) => (
                            <motion.li
                              key={r.id}
                              layout={!reduce}
                              initial={reduce ? false : { opacity: 0, scale: 0.9, y: -8 }}
                              animate={{ opacity: 1, scale: 1, y: 0 }}
                              exit={{ opacity: 0, scale: 0.9 }}
                              transition={{ type: "spring", stiffness: 420, damping: 34 }}
                              className={cn(
                                "rounded-lg border p-2.5",
                                r.stage === 3 ? "border-ink-line bg-ink-card" : "border-white/25 bg-ink-card",
                              )}
                            >
                              <p className="font-mono text-[10.5px] text-ink-muted">#{r.id}</p>
                              <p className="mt-0.5 text-[12.5px] leading-[16px] text-ink-foreground">@agent {r.ask}</p>
                              {r.agent && <p className="mt-1.5 font-mono text-[10.5px] text-ink-accent">{r.agent}</p>}
                              {r.stage === 3 && r.version && (
                                <p className="mt-1 flex items-center gap-1 font-mono text-[10.5px] text-ink-foreground">
                                  <span aria-hidden="true" className="inline-block size-2 bg-[linear-gradient(45deg,#f5f3ee_25%,transparent_25%,transparent_50%,#f5f3ee_50%,#f5f3ee_75%,transparent_75%)] bg-[length:4px_4px]" />
                                  finished in v{r.version}
                                </p>
                              )}
                            </motion.li>
                          ))}
                      </AnimatePresence>
                    </ul>
                  </div>
                ))}
              </div>
            </LayoutGroup>
          </div>

          <div>
            <h3 className="eyebrow text-band-muted">Agent signals</h3>
            <ul className="mt-3 space-y-2" aria-label="Agents and what they are doing">
              {agentNames.map((n) => (
                <AgentLight key={n} name={n} job={jobOf(n)} />
              ))}
            </ul>
            <dl className="mt-5 space-y-2.5 rounded-lg border border-white/15 p-4 text-[13px] leading-[19px]">
              <div className="flex gap-3">
                <dt aria-hidden="true" className="mt-1 size-3 shrink-0 rounded-full border-2 border-ink-muted" />
                <dd><span className="font-semibold">Hollow grey.</span> <span className="text-band-muted">Idle. Free to take a request.</span></dd>
              </div>
              <div className="flex gap-3">
                <dt aria-hidden="true" className="mt-1 size-3 shrink-0 rounded-full border-2 border-signal" />
                <dd><span className="font-semibold">Hollow ember.</span> <span className="text-band-muted">Holds a claim, about to build.</span></dd>
              </div>
              <div className="flex gap-3">
                <dt aria-hidden="true" className="mt-1 size-3 shrink-0 rounded-full bg-signal" />
                <dd><span className="font-semibold">Solid, pulsing.</span> <span className="text-band-muted">Publishing a version now.</span></dd>
              </div>
            </dl>
            <p className="mt-4 text-[12.5px] leading-[18px] text-band-muted">
              A claim lasts ten minutes by default. If the agent goes quiet, the request opens again for someone else.
            </p>
          </div>
        </div>
        <p role="status" className="sr-only">{announce}</p>
      </div>
    </section>
  );
}
