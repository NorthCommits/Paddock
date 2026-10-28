"use client";

import { animate, motion, useInView, useMotionValue, useScroll, useSpring } from "motion/react";
import { useCalm } from "@/lib/motion";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const ease = [0.2, 0, 0, 1] as const;

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduce = useCalm();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, delay, ease }}
    >
      {children}
    </motion.div>
  );
}

/** Headline that rises word by word. */
export function RiseWords({ text, className }: { text: string; className?: string }) {
  const reduce = useCalm();
  return (
    <h1 className={className} aria-label={text}>
      {text.split(" ").map((w, i) => (
        <span key={i} aria-hidden="true" className="inline-block overflow-hidden pb-[0.12em] align-bottom">
          <motion.span
            className="inline-block"
            initial={reduce ? false : { y: "110%" }}
            animate={{ y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 + i * 0.07, ease }}
          >
            {w}&nbsp;
          </motion.span>
        </span>
      ))}
    </h1>
  );
}

/** A card with a soft light that follows the pointer. The light is decoration only. */
export function SpotlightCard({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  function move(e: React.PointerEvent<HTMLDivElement>) {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  }
  return (
    <div
      ref={ref}
      onPointerMove={move}
      className={cn("group/spot relative overflow-hidden", className)}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover/spot:opacity-100"
        style={{ background: "radial-gradient(360px circle at var(--mx, 50%) var(--my, 50%), var(--primary-soft), transparent 70%)" }}
      />
      <div className="relative h-full">{children}</div>
    </div>
  );
}

/** A button wrapper that leans toward the pointer a little. Off for reduced motion. */
export function Magnetic({ children, className }: { children: ReactNode; className?: string }) {
  const calm = useCalm();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 18, mass: 0.4 });
  const sy = useSpring(y, { stiffness: 220, damping: 18, mass: 0.4 });
  return (
    <motion.div
      className={cn("inline-block", className)}
      style={{ x: sx, y: sy }}
      onPointerMove={(e) => {
        if (calm || e.pointerType !== "mouse") return;
        const r = e.currentTarget.getBoundingClientRect();
        x.set((e.clientX - (r.left + r.width / 2)) * 0.22);
        y.set((e.clientY - (r.top + r.height / 2)) * 0.32);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.div>
  );
}

/** A number that counts up the first time it scrolls into view. The final number is in the markup from the start. */
export function CountUp({ to, className }: { to: number; className?: string }) {
  const calm = useCalm();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const [v, setV] = useState(to);
  useEffect(() => {
    if (!inView || calm) return;
    const c = animate(0, to, { duration: 1.4, ease: [0.2, 0, 0, 1], onUpdate: (n) => setV(Math.round(n)) });
    return () => c.stop();
  }, [inView, calm, to]);
  return (
    <span ref={ref} className={cn("tnum", className)}>
      {v}
    </span>
  );
}
