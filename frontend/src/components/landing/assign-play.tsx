"use client";

import { motion } from "motion/react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Reveal } from "./motion-bits";

const agents = ["Claude Code", "Codex", "Cursor"];
const initial = [
  { id: "r1", text: "Add a pricing table", agent: null as string | null },
  { id: "r2", text: "Fix the chart labels", agent: null as string | null },
  { id: "r3", text: "Translate to Spanish", agent: null as string | null },
];

/** Drag an agent onto a request, or use the buttons. Both do the same thing. */
export function AssignPlay() {
  const [reqs, setReqs] = useState(initial);
  const [over, setOver] = useState<string | null>(null);

  function assign(id: string, agent: string) {
    setReqs((r) => r.map((x) => (x.id === id ? { ...x, agent } : x)));
  }
  function target(x: number, y: number) {
    const el = document.elementsFromPoint(x, y).find((e) => (e as HTMLElement).dataset?.req);
    return (el as HTMLElement | undefined)?.dataset.req ?? null;
  }

  return (
    <section id="assign" className="mx-auto max-w-[1200px] px-6 py-24" aria-labelledby="assign-title">
      <Reveal>
        <p className="eyebrow text-primary">Try it</p>
        <h2 id="assign-title" className="mt-2 max-w-[22ch] text-[32px] font-bold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
          Hand a request to an agent.
        </h2>
        <p className="mt-3 max-w-[36rem] text-[16px] leading-[26px] text-muted-foreground">
          Drag an agent onto a request. On a keyboard or a phone, press the agent buttons on the request instead.
        </p>
      </Reveal>

      <div className="mt-10 grid gap-8 md:grid-cols-[220px_1fr]">
        <div>
          <p className="eyebrow text-muted-foreground">Agents</p>
          <div className="mt-3 flex flex-wrap gap-2 md:flex-col" aria-hidden="true">
            {agents.map((a) => (
              <motion.div
                key={a}
                drag
                dragSnapToOrigin
                dragElastic={0.2}
                whileDrag={{ scale: 1.08, rotate: -3, zIndex: 20 }}
                whileHover={{ y: -2 }}
                onDrag={(e) => {
                  const p = e as PointerEvent;
                  setOver(target(p.clientX, p.clientY));
                }}
                onDragEnd={(e) => {
                  const p = e as PointerEvent;
                  const t = target(p.clientX, p.clientY);
                  if (t) assign(t, a);
                  setOver(null);
                }}
                className="relative flex h-11 cursor-grab touch-none select-none items-center gap-2 rounded-full bg-primary px-4 text-[14px] font-medium text-primary-foreground active:cursor-grabbing"
              >
                <span className="size-2 rounded-full bg-signal" />
                {a}
              </motion.div>
            ))}
          </div>
        </div>

        <ul className="space-y-3">
          {reqs.map((r) => (
            <li
              key={r.id}
              data-req={r.id}
              className={cn(
                "rounded-xl border bg-card p-4 transition-[border-color,background-color,transform] duration-200",
                over === r.id ? "scale-[1.01] border-primary bg-primary-soft" : "border-border",
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-[15px] font-medium text-foreground">{r.text}</p>
                <motion.span
                  key={r.agent ?? "none"}
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className={cn(
                    "rounded-full px-3 py-1 text-[12px] font-semibold",
                    r.agent ? "bg-primary text-primary-foreground" : "border border-input-border text-muted-foreground",
                  )}
                >
                  {r.agent ? `Claimed by ${r.agent}` : "Open"}
                </motion.span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {agents.map((a) => (
                  <button
                    key={a}
                    onClick={() => assign(r.id, a)}
                    aria-label={`Assign ${a} to ${r.text}`}
                    className="h-9 rounded-full border border-input-border px-3 text-[13px] text-foreground transition-colors duration-200 hover:bg-muted"
                  >
                    {a}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-4">
        <button onClick={() => setReqs(initial)} className="h-9 rounded-full px-3 text-[13px] text-primary underline underline-offset-4">
          Reset
        </button>
      </div>
    </section>
  );
}
