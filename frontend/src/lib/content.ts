"use client";

import { useEffect, useState } from "react";

// Free hosting puts idle servers to sleep, and a sleeping server answers with its own "waking up"
// screen instead of our page. The content server lets this app read its /healthz answer, so we ask
// it directly and only show a page once it has answered properly.

const STAY_AWAKE = 8 * 60 * 1000; // hosts sleep after about 15 quiet minutes
const TRUST = 4 * 60 * 1000; // how long one good answer is trusted
const GIVE_UP = 90 * 1000; // after this, show the page anyway rather than wait forever

const proven = new Map<string, number>();

async function answers(origin: string): Promise<boolean> {
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), 8000);
  try {
    const res = await fetch(`${origin}/healthz`, { cache: "no-store", signal: stop.signal });
    const body = (await res.json()) as { status?: string };
    const ok = body.status === "ok";
    if (ok) proven.set(origin, Date.now());
    return ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** Resolves once the content server answers (or after a long wait, so the screen never hangs). */
export async function waitUntilAwake(url: string, signal?: AbortSignal): Promise<void> {
  const origin = new URL(url).origin;
  if (Date.now() - (proven.get(origin) ?? 0) < TRUST) return;
  const giveUp = Date.now() + GIVE_UP;
  for (let n = 0; Date.now() < giveUp && !signal?.aborted; n++) {
    if (await answers(origin)) return;
    await new Promise((r) => setTimeout(r, Math.min(1000 + n * 500, 4000)));
  }
}

/** True once the content server for this address is awake. Keeps it awake while the screen is open. */
export function useContentAwake(url: string | undefined): boolean {
  const origin = url ? new URL(url).origin : null;
  const [awake, setAwake] = useState<string | null>(null);

  useEffect(() => {
    if (!origin) return;
    const stop = new AbortController();
    void waitUntilAwake(origin, stop.signal).then(() => {
      if (!stop.signal.aborted) setAwake(origin);
    });
    const keep = setInterval(() => void answers(origin), STAY_AWAKE);
    return () => {
      stop.abort();
      clearInterval(keep);
    };
  }, [origin]);

  return origin !== null && awake === origin;
}
