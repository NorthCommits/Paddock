"use client";

import { useEffect } from "react";
import { warmServers } from "@/lib/warm";

// Wakes the servers when a visit starts and when someone comes back to a tab that sat idle.
export function Warm() {
  useEffect(() => {
    warmServers();
    const onVisible = () => {
      if (document.visibilityState === "visible") warmServers();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);
  return null;
}
