"use client";

import { motion,  } from "motion/react";
import { useCalm } from "@/lib/motion";
import { cn } from "@/lib/utils";

export const MARK_PATH =
  "M68 36H143A53 53 0 0 1 194.62 77H157.73A19 19 0 0 0 143 70H102V108H143A19 19 0 0 0 157.73 101H194.62A53 53 0 0 1 143 142H102V220H68Z";

/** The app icon: ink Gate P on an ember rounded square. Ember is the brand's 10% accent. */
export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 256 256" aria-hidden="true">
      <rect width="256" height="256" rx="58" fill="var(--signal)" />
      <path transform="translate(20 4) scale(0.88)" fill="#0f1115" d={MARK_PATH} />
    </svg>
  );
}

export function Wordmark({
  size = 20,
  className,
  tone = "default",
}: {
  size?: number;
  className?: string;
  tone?: "default" | "band";
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <Mark size={size} />
      <span
        className={cn("font-display font-semibold tracking-[-0.02em]", tone === "band" ? "text-band-foreground" : "text-foreground")}
        style={{ fontSize: size * 0.85 }}
      >
        Paddock
      </span>
    </span>
  );
}

/** Large Gate P with an agent dot that travels through the gate. */
export function GateMark({ className, dot = "var(--signal)" }: { className?: string; dot?: string }) {
  const reduce = useCalm();
  return (
    <svg viewBox="0 0 256 256" aria-hidden="true" className={className}>
      <path transform="translate(-4 0)" fill="currentColor" d={MARK_PATH} />
      <motion.circle
        r="7"
        cy="73.5"
        fill={dot}
        initial={{ cx: 246 }}
        animate={reduce ? { cx: 176 } : { cx: [246, 176, 176, 246], opacity: [0, 1, 1, 0] }}
        transition={{ duration: 4.5, repeat: Infinity, ease: [0.32, 0.72, 0, 1], times: [0, 0.3, 0.7, 1] }}
      />
    </svg>
  );
}

/** A row of fence posts that grow in. The brand motif. */
export function Fence({ className }: { className?: string }) {
  const posts = Array.from({ length: 28 });
  return (
    <div aria-hidden="true" className={cn("flex items-end justify-between gap-2", className)}>
      {posts.map((_, i) => (
        <motion.span
          key={i}
          className="w-[3px] origin-bottom rounded-full bg-border"
          style={{ height: i % 4 === 0 ? 28 : 18 }}
          initial={{ scaleY: 0 }}
          whileInView={{ scaleY: 1 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ duration: 0.5, delay: i * 0.02, ease: [0.2, 0, 0, 1] }}
        />
      ))}
    </div>
  );
}
