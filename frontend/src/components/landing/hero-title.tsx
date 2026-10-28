"use client";

import { motion,  } from "motion/react";
import { useCalm } from "@/lib/motion";

const ease = [0.2, 0, 0, 1] as const;

function Word({ children, i, className }: { children: string; i: number; className?: string }) {
  const reduce = useCalm();
  return (
    <span aria-hidden="true" className="inline-block overflow-hidden pb-[0.14em] align-bottom">
      <motion.span
        className={`inline-block ${className ?? ""}`}
        initial={reduce ? false : { y: "115%", rotate: 4 }}
        animate={{ y: 0, rotate: 0 }}
        transition={{ duration: 0.8, delay: 0.15 + i * 0.09, ease }}
      >
        {children}&nbsp;
      </motion.span>
    </span>
  );
}

/** The hero headline. Words rise into place one by one. Screen readers get the plain sentence. */
export function HeroTitle() {
  return (
    <h1
      aria-label="Your agents ship. You decide."
      className="font-display text-[52px] font-bold leading-[0.92] tracking-[-0.055em] text-ink-foreground sm:text-[84px] lg:text-[124px]"
    >
      <span className="block">
        <Word i={0}>Your</Word>
        <Word i={1}>agents</Word>
        <Word i={2}>ship.</Word>
      </span>
      <span className="block">
        <Word i={3}>You</Word>
        <Word i={4} className="serif-accent text-signal">
          decide.
        </Word>
      </span>
    </h1>
  );
}
