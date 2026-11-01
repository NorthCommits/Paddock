"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { WakeHint } from "@/components/wake-hint";
import type { Anchor } from "@/lib/api";
import { useContentAwake, waitUntilAwake } from "@/lib/content";
import { cn } from "@/lib/utils";

export type FrameMark = {
  id: string;
  n: number;
  anchor: Anchor;
  preview?: { author: string; text: string; replies: number; resolved: boolean };
};
export type FramePeer = { block: string; name: string; color: string; kind: "look" | "select" };
export type FrameReaction = { block: string; key: string; count: number; mine: boolean; who: string[] };

type Slot = { id: number; src: string; version: number; ready: boolean; bridge: boolean; tries: number };

function tagOf(name: string): string {
  const w = name.trim().split(/\s+/);
  return ((w[0]?.[0] ?? "?") + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase();
}

const BLOCK = /^[A-Za-z0-9_-]{1,64}$/;
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
  commentMode = false,
  shareFocus = false,
  peers = [],
  reactions = [],
  canReact = false,
  onComment,
  onMark,
  onMissing,
  onFocus,
  onReact,
  onExitMode,
}: {
  url: string | undefined;
  version: number | undefined;
  title: string;
  marks?: FrameMark[];
  focus?: { anchor: Anchor; key: number } | null;
  commentMode?: boolean;
  shareFocus?: boolean;
  peers?: FramePeer[];
  reactions?: FrameReaction[];
  canReact?: boolean;
  onComment?: (anchor: Anchor) => void;
  onMark?: (id: string) => void;
  onMissing?: () => void;
  onFocus?: (block: string | null, kind: "look" | "select") => void;
  onReact?: (block: string, key: string, on: boolean) => void;
  onExitMode?: () => void;
}) {
  const awake = useContentAwake(url);
  const [slots, setSlots] = useState<Slot[]>([]);
  const slotsRef = useRef<Slot[]>([]);
  const frames = useRef(new Map<number, HTMLIFrameElement | null>());
  const counter = useRef(1);
  const latest = useRef({ url, version });
  const callbacks = useRef({ onComment, onMark, onMissing, onFocus, onReact, onExitMode });

  useEffect(() => {
    slotsRef.current = slots;
    latest.current = { url, version };
    callbacks.current = { onComment, onMark, onMissing, onFocus, onReact, onExitMode };
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
      const d = e.data as {
        paddock?: boolean;
        type?: string;
        anchor?: Anchor;
        id?: unknown;
        kind?: unknown;
        block?: unknown;
        key?: unknown;
        on?: unknown;
        comment?: unknown;
        x?: unknown;
        y?: unknown;
      } | null;
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
      else if (d.type === "focus") {
        const id = typeof d.id === "string" && BLOCK.test(d.id) ? d.id : null;
        callbacks.current.onFocus?.(id, d.kind === "select" ? "select" : "look");
      } else if (d.type === "react") {
        // A reaction is an action as the viewer, so it needs a real click or tap just now.
        const active = typeof navigator !== "undefined" && navigator.userActivation ? navigator.userActivation.isActive : true;
        if (active && typeof d.block === "string" && BLOCK.test(d.block) && typeof d.key === "string") {
          callbacks.current.onReact?.(d.block, d.key, d.on === true);
        }
      } else if (d.type === "mode" && d.comment === false) callbacks.current.onExitMode?.();
      else if (d.type === "markhover" && typeof d.id === "string" && typeof d.x === "number" && typeof d.y === "number") {
        const box = frames.current.get(slot.id)?.getBoundingClientRect();
        if (box) setHover({ id: d.id, x: box.left + d.x, y: box.top + d.y });
      } else if (d.type === "markleave") setHover(null);
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
  const post = useCallback(
    (msg: Record<string, unknown>) => {
      if (readyId === undefined) return;
      const target = slotsRef.current.find((s) => s.id === readyId);
      if (target) frames.current.get(readyId)?.contentWindow?.postMessage({ paddock: true, ...msg }, new URL(target.src).origin);
    },
    [readyId],
  );
  useEffect(() => {
    if (readyId === undefined) return;
    // Comment words stay in the app: the page only gets where to draw each number.
    post({ type: "marks", marks: marks.map((m) => ({ id: m.id, n: m.n, anchor: m.anchor })) });
  }, [marks, readyId, post]);

  // The helper script learns the viewer's state whenever it changes, and again after each new frame.
  useEffect(() => {
    if (readyId !== undefined) post({ type: "mode", comment: commentMode });
  }, [commentMode, readyId, post]);
  useEffect(() => {
    if (readyId !== undefined) post({ type: "share", on: shareFocus });
  }, [shareFocus, readyId, post]);
  useEffect(() => {
    if (readyId !== undefined) post({ type: "peers", peers: peers.map((p) => ({ block: p.block, color: p.color, kind: p.kind, tag: tagOf(p.name) })) });
  }, [peers, readyId, post]);
  useEffect(() => {
    if (readyId !== undefined) {
      post({ type: "reactions", items: reactions.map((r) => ({ block: r.block, key: r.key, count: r.count, mine: r.mine })), can: canReact });
    }
  }, [reactions, canReact, readyId, post]);

  const shownFocus = useRef(0);
  useEffect(() => {
    if (!focus || readyId === undefined || shownFocus.current === focus.key) return;
    shownFocus.current = focus.key;
    const target = slotsRef.current.find((s) => s.id === readyId);
    if (target) frames.current.get(readyId)?.contentWindow?.postMessage({ paddock: true, type: "show", anchor: focus.anchor }, new URL(target.src).origin);
  }, [focus, readyId]);

  const showing = slots.some((s) => s.ready);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const hovered = hover ? marks.find((m) => m.id === hover.id)?.preview : undefined;

  // Escape leaves comment mode even when the keyboard focus is outside the page frame.
  useEffect(() => {
    if (!commentMode) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") callbacks.current.onExitMode?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [commentMode]);

  return (
    <>
      {hover && hovered && (
        <div
          role="tooltip"
          style={{ position: "fixed", left: Math.max(8, Math.min(hover.x - 200, window.innerWidth - 256)), top: hover.y + 6 }}
          className="pointer-events-none z-30 w-60 rounded-xl border border-border bg-card p-3 text-[13px] text-foreground shadow-float"
        >
          <b className="block text-[12px]">{hovered.author}</b>
          <p className="mt-1 line-clamp-3 break-words">{hovered.text}</p>
          <small className="mt-1.5 block text-[11px] text-muted-foreground">
            {hovered.resolved ? "Resolved. " : ""}
            {hovered.replies === 1 ? "1 reply" : `${hovered.replies} replies`}
          </small>
        </div>
      )}
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
