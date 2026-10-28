"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { useCalm } from "@/lib/motion";
import { useRef } from "react";

const COLS = 56;
const ROWS = 26;
const CELL = 28;

/** A small seeded random generator, so the pattern is the same on the server and in the browser. */
function rng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

const cells = (() => {
  const r = rng(26);
  const out: { x: number; y: number; kind: "indigo" | "ember"; delay: number; dur: number; o: number }[] = [];
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      const v = r();
      if (v < 0.085) out.push({ x, y, kind: "indigo", delay: 0, dur: 0, o: 0.15 + r() * 0.35 });
      else if (v > 0.992) out.push({ x, y, kind: "ember", delay: r() * 6, dur: 3.5 + r() * 3, o: 1 });
    }
  }
  return out;
})();

/**
 * The hero backdrop: a field of quiet indigo cells with a few ember cells that blink, like agents
 * reporting in. It is decoration only, hidden from assistive technology, and holds still for
 * people who prefer reduced motion.
 */
export function SignalField({ className }: { className?: string }) {
  const reduce = useCalm();
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : 90]);

  return (
    <div ref={ref} aria-hidden="true" className={className}>
      <motion.svg
        style={{ y }}
        viewBox={`0 0 ${COLS * CELL} ${ROWS * CELL}`}
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 h-full w-full"
      >
        <defs>
          <pattern id="grid" width={CELL} height={CELL} patternUnits="userSpaceOnUse">
            <path d={`M${CELL} 0H0V${CELL}`} fill="none" stroke="rgba(245,243,238,0.05)" strokeWidth="1" />
          </pattern>
          <radialGradient id="fade" cx="50%" cy="30%" r="75%">
            <stop offset="0%" stopColor="white" />
            <stop offset="100%" stopColor="black" />
          </radialGradient>
          <mask id="mask">
            <rect width="100%" height="100%" fill="url(#fade)" />
          </mask>
        </defs>
        <g mask="url(#mask)">
          <rect width="100%" height="100%" fill="url(#grid)" />
          {cells.map((c) => (
            <rect
              key={`${c.x}-${c.y}`}
              x={c.x * CELL + 3}
              y={c.y * CELL + 3}
              width={CELL - 6}
              height={CELL - 6}
              rx="3"
              fill={c.kind === "ember" ? "#ff6b4a" : "#3b33c9"}
              opacity={c.kind === "indigo" ? c.o : 0.06}
              style={
                c.kind === "ember" && !reduce
                  ? { animation: `cell ${c.dur}s ease-in-out ${c.delay}s infinite` }
                  : c.kind === "ember"
                    ? { opacity: 0.4 }
                    : undefined
              }
            />
          ))}
        </g>
      </motion.svg>
    </div>
  );
}
