"use client";

import "locomotive-scroll/locomotive-scroll.css";
import { motion, useReducedMotion, useScroll, useSpring } from "motion/react";
import { useEffect } from "react";

/**
 * Smooth scrolling for the landing page (Locomotive Scroll v5, built on Lenis).
 * It keeps the native scrollbar, so sticky headers, anchors and in-view reveals still work.
 * It is switched off when the person prefers reduced motion. Touch devices keep native momentum.
 */
export function SmoothScroll() {
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 28, mass: 0.4 });

  useEffect(() => {
    if (reduce) return;
    let scroll: { destroy: () => void } | undefined;
    let cancelled = false;
    import("locomotive-scroll").then(({ default: LocomotiveScroll }) => {
      if (cancelled) return;
      scroll = new LocomotiveScroll({
        lenisOptions: { lerp: 0.085, wheelMultiplier: 0.95, anchors: true },
      });
    });
    return () => {
      cancelled = true;
      scroll?.destroy();
    };
  }, [reduce]);

  return (
    <motion.div
      aria-hidden="true"
      className="fixed inset-x-0 top-0 z-40 h-[2px] origin-left bg-primary"
      style={{ scaleX }}
    />
  );
}
