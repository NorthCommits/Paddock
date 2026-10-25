"use client";

import { motion } from "motion/react";
import { FileText } from "lucide-react";
import { GateMark } from "@/components/brand";
import { LinkButton } from "@/components/ui/button";

const ghosts = [
  { t: "Q3 revenue report", m: "v3 · 2 comments" },
  { t: "Onboarding flow mockup", m: "v1 · 1 request" },
  { t: "Launch checklist", m: "v5 · up to date" },
];

export default function Page() {
  return (
    <>
      <h1 className="text-[22px] font-semibold leading-7 tracking-[-0.01em] text-foreground">Pages</h1>
      <div className="mt-6 grid items-center gap-10 rounded-xl border border-border bg-card p-8 shadow-card md:grid-cols-[1fr_300px]">
        <div>
          <GateMark className="size-14 text-foreground" />
          <h2 className="mt-5 text-[22px] font-semibold leading-7 tracking-[-0.01em] text-foreground">
            The gate is open, the paddock is empty
          </h2>
          <p className="mt-2 max-w-[38ch] text-[15px] leading-[22px] text-muted-foreground">
            Pages appear here as soon as one of your agents publishes. Connect an agent to send the first one.
          </p>
          <div className="mt-6">
            <LinkButton href="/connect" size="lg">Connect an agent</LinkButton>
          </div>
        </div>
        <div aria-hidden="true">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.06em] text-subtle">What you will see</p>
          <ul className="space-y-2">
            {ghosts.map((g, i) => (
              <motion.li
                key={g.t}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 0.7 - i * 0.15, x: 0 }}
                transition={{ delay: 0.3 + i * 0.12, duration: 0.5, ease: [0.2, 0, 0, 1] }}
                className="flex items-center gap-3 rounded-lg border border-dashed border-border px-3 py-2.5"
              >
                <FileText size={16} className="text-subtle" />
                <div>
                  <p className="text-[13px] font-medium text-foreground">{g.t}</p>
                  <p className="text-[12px] text-muted-foreground">{g.m}</p>
                </div>
              </motion.li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
