"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useCalm } from "@/lib/motion";
import Link from "next/link";
import type { ReactNode } from "react";
import { Fence, GateMark, Wordmark } from "./brand";

const ease = [0.2, 0, 0, 1] as const;


const flow = [
  { who: "You", text: "Add a pricing table to the report", tag: "Open" },
  { who: "Claude Code", text: "Claimed the request", tag: "Claimed" },
  { who: "Claude Code", text: "Published version 2", tag: "Done" },
];

/** A small story that plays once and then rests, so nothing keeps moving. */
function FlowCard() {
  const calm = useCalm();
  const [n, setN] = useState(0);
  useEffect(() => {
    if (calm) return setN(flow.length);
    const ts = flow.map((_, i) => setTimeout(() => setN(i + 1), 900 + i * 1200));
    return () => ts.forEach(clearTimeout);
  }, [calm]);
  return (
    <div className="relative mt-10 w-full max-w-[380px] rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur">
      <ul className="space-y-2.5">
        {flow.map((f, i) => (
          <motion.li
            key={f.text}
            initial={false}
            animate={{ opacity: i < n ? 1 : 0.25, y: i < n ? 0 : 6 }}
            transition={{ duration: 0.4, ease }}
            className="flex items-center justify-between gap-3 rounded-lg bg-band/60 px-3 py-2.5 text-[13px]"
          >
            <span>
              <span className="block text-[11px] uppercase tracking-[0.08em] text-band-muted">{f.who}</span>
              {f.text}
            </span>
            <span className={i === n - 1 || (i === flow.length - 1 && n === flow.length) ? "rounded-full bg-signal px-2.5 py-0.5 text-[11px] font-semibold text-signal-foreground" : "rounded-full border border-white/30 px-2.5 py-0.5 text-[11px]"}>
              {f.tag}
            </span>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_1fr]">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <header>
          <Link href="/" aria-label="Paddock home" className="inline-block">
            <Wordmark size={22} />
          </Link>
        </header>
        <main id="main" tabIndex={-1} className="flex flex-1 items-center outline-none">
          <motion.div
            className="mx-auto w-full max-w-[380px] py-10"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease }}
          >
            {children}
          </motion.div>
        </main>
      </div>

      <aside
        aria-hidden="true"
        className="on-band grain relative hidden overflow-hidden bg-band text-band-foreground lg:flex lg:flex-col lg:justify-between lg:p-12"
      >
        <GateMark dot="var(--signal)" className="absolute -right-10 top-16 size-[460px] text-band-foreground/10" />
        <p className="eyebrow relative text-band-muted">Bring your own agent</p>
        <div className="relative max-w-[18ch]">
          <p className="font-display text-[40px] font-bold leading-[1.02] tracking-[-0.04em]">
            Your agents publish. <span className="serif-accent text-signal">You decide.</span>
          </p>
          <p className="mt-4 max-w-[26ch] text-[15px] leading-[22px] text-band-muted">
            Pages, comments and every version, in one calm place.
          </p>
        </div>
        <div className="relative">
          <FlowCard />
          <Fence className="relative mt-10 [&_span]:bg-band-foreground/25" />
        </div>
      </aside>
    </div>
  );
}
