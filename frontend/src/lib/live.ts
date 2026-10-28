"use client";

import { useEffect, useRef } from "react";
import { bearer } from "./api";

export type LiveEvent = {
  id: number;
  type: string;
  page_id: string | null;
  created_at: string;
  data: Record<string, unknown>;
};

// Called with each event. "resync" means events may have been missed, so refetch what is on screen.
export type LiveHandler = (event: LiveEvent | "resync") => void;

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      resolve();
    });
  });

function read(block: string): { id: string | null; event: string; data: string } | null {
  let id: string | null = null;
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue; // a ping or the opening comment
    if (line.startsWith("id: ")) id = line.slice(4);
    else if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data.push(line.slice(6));
  }
  return data.length ? { id, event, data: data.join("\n") } : null;
}

/**
 * Keeps a live stream open to the API and calls the handler for each event.
 * It reconnects by itself, asks for what it missed with Last-Event-ID, and tells the handler to refetch
 * after any gap. The browser's EventSource cannot send our sign-in header, so this uses fetch.
 */
export function useLive(path: string | null, onEvent: LiveHandler) {
  const handler = useRef(onEvent);
  useEffect(() => {
    handler.current = onEvent;
  });

  useEffect(() => {
    if (!path) return;
    const stop = new AbortController();
    let last: string | null = null;
    let wait = 1000;
    let connected = false;

    (async () => {
      while (!stop.signal.aborted) {
        try {
          const token = await bearer();
          const headers: Record<string, string> = {};
          if (token) headers["Authorization"] = `Bearer ${token}`;
          if (last) headers["Last-Event-ID"] = last;
          const res = await fetch(`/api${path}`, { headers, signal: stop.signal, credentials: "same-origin" });
          // No access or nothing there: asking again will not help.
          if (res.status === 403 || res.status === 404) return;
          if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
          wait = 1000;
          // After a drop, anything missed before the first event id is unknown, so refetch.
          if (connected) handler.current("resync");
          connected = true;

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            let cut = buffer.indexOf("\n\n");
            while (cut >= 0) {
              const frame = read(buffer.slice(0, cut));
              buffer = buffer.slice(cut + 2);
              if (frame?.event === "resync") handler.current("resync");
              else if (frame) {
                if (frame.id) last = frame.id;
                handler.current(JSON.parse(frame.data) as LiveEvent);
              }
              cut = buffer.indexOf("\n\n");
            }
          }
        } catch {
          if (stop.signal.aborted) return;
        }
        await sleep(wait, stop.signal);
        wait = Math.min(wait * 2, 30_000);
      }
    })();

    return () => stop.abort();
  }, [path]);
}
