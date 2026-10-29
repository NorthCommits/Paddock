"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { WakeHint } from "@/components/wake-hint";
import type { Anchor } from "@/lib/api";
import { useContentAwake, waitUntilAwake } from "@/lib/content";
import { cn } from "@/lib/utils";

export type FrameMark = { id: string; n: number; anchor: Anchor };

type Slot = { id: number; src: string; version: number; ready: boolean; bridge: boolean; tries: number };

const LOAD_PATIENCE = 25 * 1000; // a frame that has not reported in by then is loaded again
const MAX_TRIES = 4;

/**
 * Shows a page on the content origin. It keeps the same frame when the version changes and asks the
 * page's helper script to update only the parts that differ. When that is not possible it loads the
 * new version behind the old one and fades between them. A frame stays hidden until it reports in,
 * and the content server must have answered first, so the host's "waking up" screen never shows.
 */
export function PageFrame({
  url,
  version,
  title,
  marks = [],
  focus = null,
  onComment,
  onMark,
  onMissing,
}: {
  url: string | undefined;
  version: number | undefined;
  title: string;
  marks?: FrameMark[];
  focus?: { anchor: Anchor; key: number } | null;
  onComment?: (anchor: Anchor) => void;
  onMark?: (id: string) => void;
  onMissing?: () => void;
}) {
  const awake = useContentAwake(url);
  const [slots, setSlots] = useState<Slot[]>([]);
  const slotsRef = useRef<Slot[]>([]);
  const frames = useRef(new Map<number, HTMLIFrameElement | null>());
  const counter = useRef(1);
  const latest = useRef({ url, version });
  const callbacks = useRef({ onComment, onMark, onMissing });

  useEffect(() => {
    slotsRef.current = slots;
    latest.current = { url, version };
    callbacks.current = { onComment, onMark, onMissing };
  });

  const addSlot = useCallback((src: string, v: number) => {
    setSlots((s) => [...s, { id: counter.current++, src, version: v, ready: false, bridge: true, tries: 0 }]);
  }, []);

  // The first frame, once the content server has answered.
  useEffect(() => {
    if (awake && url && version !== undefined && slotsRef.current.length === 0) addSlot(url, version);
  }, [awake, url, version, addSlot]);

  // A new version: patch the frame we have, or load it behind the old one.
  useEffect(() => {
    const top = slotsRef.current[slotsRef.current.length - 1];
    if (!top || !url || version === undefined || top.version === version) return;
    if (top.ready && top.bridge) {
      frames.current.get(top.id)?.contentWindow?.postMessage({ paddock: true, type: "patch", url }, new URL(top.src).origin);
      setSlots((s) => s.map((x) => (x.id === top.id ? { ...x, version } : x)));
    } else {
      addSlot(url, version);
    }
  }, [url, version, addSlot]);

  const newest = slots.length ? slots[slots.length - 1] : undefined;

  const reloadLatest = useCallback(async () => {
    const { url: u, version: v } = latest.current;
    if (!u || v === undefined) return;
    await waitUntilAwake(u);
    addSlot(u, v);
  }, [addSlot]);

  // Messages from the helper script inside a frame.
  useEffect(() => {
    function onMessage(e: MessageEvent) {
      const d = e.data as { paddock?: boolean; type?: string; anchor?: Anchor; id?: unknown } | null;
      if (!d || d.paddock !== true) return;
      const slot = slotsRef.current.find((s) => frames.current.get(s.id)?.contentWindow === e.source);
      if (!slot || e.origin !== new URL(slot.src).origin) return;
      const top = slotsRef.current[slotsRef.current.length - 1];
      if (d.type === "ready") {
        setSlots((s) => s.map((x) => (x.id === slot.id ? { ...x, ready: true } : x)));
        // Once the new frame is showing, the older ones can go.
        setTimeout(() => {
          setSlots((s) => {
            let k = -1;
            s.forEach((x, i) => {
              if (x.ready) k = i;
            });
            return k > 0 ? s.slice(k) : s;
          });
        }, 400);
      } else if (d.type === "comment" && d.anchor) callbacks.current.onComment?.(d.anchor);
      else if (d.type === "mark") callbacks.current.onMark?.(String(d.id));
      else if (d.type === "missing") callbacks.current.onMissing?.();
      else if ((d.type === "reload" || d.type === "patch-failed") && top && top.id === slot.id) void reloadLatest();
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [reloadLatest]);

  // A frame that never reports in (still loading, or the server dozed off) is loaded again.
  const waitingId = newest && !newest.ready ? `${newest.id}-${newest.tries}` : null;
  useEffect(() => {
    if (!waitingId || !newest) return;
    const id = newest.id;
    const t = setTimeout(() => {
      setSlots((s) =>
        s.map((x) => {
          if (x.id !== id || x.ready) return x;
          return x.tries + 1 >= MAX_TRIES ? { ...x, ready: true, bridge: false } : { ...x, tries: x.tries + 1 };
        }),
      );
    }, LOAD_PATIENCE);
    return () => clearTimeout(t);
  }, [waitingId]);

  // Numbered markers for open comments, and scrolling to a comment's spot.
  const readySlot = [...slots].reverse().find((s) => s.ready && s.bridge);
  const readyId = readySlot?.id;
  useEffect(() => {
    if (readyId === undefined) return;
    const list = marks.map((m) => ({ id: m.id, n: m.n, anchor: m.anchor }));
    const target = slotsRef.current.find((s) => s.id === readyId);
    if (target) frames.current.get(readyId)?.contentWindow?.postMessage({ paddock: true, type: "marks", marks: list }, new URL(target.src).origin);
  }, [marks, readyId]);

  const shownFocus = useRef(0);
  useEffect(() => {
    if (!focus || readyId === undefined || shownFocus.current === focus.key) return;
    shownFocus.current = focus.key;
    const target = slotsRef.current.find((s) => s.id === readyId);
    if (target) frames.current.get(readyId)?.contentWindow?.postMessage({ paddock: true, type: "show", anchor: focus.anchor }, new URL(target.src).origin);
  }, [focus, readyId]);

  const showing = slots.some((s) => s.ready);

  return (
    <>
      {!showing && (
        <div className="space-y-3 p-6">
          <Skeleton className="h-[40vh] w-full" />
          <WakeHint what="The page server" />
        </div>
      )}
      {slots.map((s, i) => (
        <iframe
          key={`${s.id}-${s.tries}`}
          ref={(el) => {
            if (el) frames.current.set(s.id, el);
            else frames.current.delete(s.id);
          }}
          title={i === slots.length - 1 ? title : `${title} (previous)`}
          aria-hidden={i === slots.length - 1 ? undefined : true}
          src={s.src}
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-downloads"
          referrerPolicy="no-referrer"
          onLoad={() => {
            // A page without the helper (not HTML) never reports in, so show it after a short wait.
            setTimeout(() => {
              setSlots((all) => all.map((x) => (x.id === s.id && !x.ready ? { ...x, ready: true, bridge: false } : x)));
            }, 4000);
          }}
          className={cn(
            "absolute inset-0 size-full border-0 transition-opacity duration-300 motion-reduce:transition-none",
            s.ready ? "bg-white opacity-100" : "pointer-events-none bg-transparent opacity-0",
          )}
        />
      ))}
    </>
  );
}
