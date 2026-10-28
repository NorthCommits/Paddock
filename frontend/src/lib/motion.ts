"use client";

import { useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

/**
 * True when the person asked their system for less motion.
 * It is false during server rendering and the first client render, so the server and the browser
 * agree on the markup (no hydration mismatch), and it switches to the real answer right after.
 */
export function useCalm(): boolean {
  const reduce = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted && reduce === true;
}
