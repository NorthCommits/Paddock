"use client";

import "locomotive-scroll/locomotive-scroll.css";
import { useCalm } from "@/lib/motion";
import { useEffect } from "react";

/**
 * Smooth scrolling for the landing page (Locomotive Scroll v5, built on Lenis).
 * It keeps the native scrollbar, so sticky headers, anchors and in-view reveals still work.
 * It is switched off when the person prefers reduced motion. Touch devices keep native momentum.
 */
export function SmoothScroll() {
  const reduce = useCalm();

  useEffect(() => {
    if (reduce) return;
    let scroll: { destroy: () => void } | undefined;
    let cancelled = false;
    import("locomotive-scroll").then(({ default: LocomotiveScroll }) => {
      if (cancelled) return;
      scroll = new LocomotiveScroll({
        lenisOptions: { lerp: 0.085, wheelMultiplier: 0.95, anchors: { offset: -56 } },
      });
    });
    return () => {
      cancelled = true;
      scroll?.destroy();
    };
  }, [reduce]);

  return null;
}
