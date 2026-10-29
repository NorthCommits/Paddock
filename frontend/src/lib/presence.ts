"use client";

import { useEffect } from "react";
import { api } from "./api";

const EVERY = 20_000; // the server counts someone as here for 45 seconds after the last beat

/** Tells the page you are looking at it. It stops while the tab is hidden and says goodbye on leaving. */
export function usePresence(pageId: string | null) {
  useEffect(() => {
    if (!pageId) return;
    const path = `/v1/pages/${pageId}/presence`;
    let timer: ReturnType<typeof setInterval> | undefined;

    const beat = () => void api(path, { method: "POST" }).catch(() => {});
    const leave = () => void api(path, { method: "DELETE" }).catch(() => {});
    const start = () => {
      beat();
      timer = setInterval(beat, EVERY);
    };
    const stop = () => {
      clearInterval(timer);
      timer = undefined;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        if (!timer) start();
      } else if (timer) {
        stop();
        leave();
      }
    };

    if (document.visibilityState === "visible") start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      if (timer) {
        stop();
        leave();
      }
    };
  }, [pageId]);
}

// Six colours, each at least 4.5:1 against white initials (measured 5.02 to 7.90).
const RING = ["#b4530a", "#0f766e", "#4338ca", "#be185d", "#15803d", "#9333ea"];

/** A steady colour for a person, so they look the same to everyone. */
export function ringColor(userId: string): string {
  let h = 0;
  for (let i = 0; i < userId.length; i++) h = (h * 31 + userId.charCodeAt(i)) >>> 0;
  return RING[h % RING.length];
}

export function initials(p: { display_name: string; handle: string }): string {
  const words = (p.display_name || p.handle).trim().split(/\s+/);
  return ((words[0]?.[0] ?? "") + (words.length > 1 ? words[words.length - 1][0] : "")).toUpperCase();
}
