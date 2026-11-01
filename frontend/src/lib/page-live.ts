"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { api } from "./api";
import type { LiveEvent } from "./live";
import { ringColor } from "./presence";
import type { FramePeer, FrameReaction } from "@/components/page-frame";

const KEEP = "paddock-share-focus";
const NONE: FrameReaction[] = [];
const PEER_LIFE = 8000; // someone who has not moved for this long stops showing

/** Whether the reader lets others see which part they are on. On unless they turn it off. */
export function useShareFocus(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(true);
  useEffect(() => {
    try {
      if (localStorage.getItem(KEEP) === "off") setOn(false);
    } catch {
      /* storage can be blocked */
    }
  }, []);
  const set = useCallback((value: boolean) => {
    setOn(value);
    try {
      localStorage.setItem(KEEP, value ? "on" : "off");
    } catch {
      /* the choice just will not be remembered */
    }
  }, []);
  return [on, set];
}

type Seen = { name: string; block: string; kind: "look" | "select"; at: number };

/**
 * Where other people are on the page. Nothing is stored: each place arrives as a live event and is
 * forgotten after a few seconds. Sending happens only while someone else is here and sharing is on.
 */
export function usePeers(pageId: string, meId: string, share: boolean, othersHere: boolean) {
  const [seen, setSeen] = useState<Record<string, Seen>>({});

  const onEvent = useCallback(
    (e: LiveEvent) => {
      if (e.type !== "focus.changed") return;
      const d = e.data as { user_id?: string; name?: string; block?: string | null; kind?: string };
      if (!d.user_id || d.user_id === meId) return;
      const uid = d.user_id;
      setSeen((s) => {
        const next = { ...s };
        if (typeof d.block === "string") {
          next[uid] = { name: String(d.name ?? "Someone"), block: d.block, kind: d.kind === "select" ? "select" : "look", at: Date.now() };
        } else {
          delete next[uid];
        }
        return next;
      });
    },
    [meId],
  );

  // Old places fall away on their own.
  const any = Object.keys(seen).length > 0;
  useEffect(() => {
    if (!any) return;
    const t = setInterval(() => {
      setSeen((s) => {
        const now = Date.now();
        const next = Object.fromEntries(Object.entries(s).filter(([, v]) => now - v.at < PEER_LIFE));
        return Object.keys(next).length === Object.keys(s).length ? s : next;
      });
    }, 2000);
    return () => clearInterval(t);
  }, [any]);

  const peers: FramePeer[] = useMemo(
    () => Object.entries(seen).map(([uid, v]) => ({ block: v.block, name: v.name, kind: v.kind, color: ringColor(uid) })),
    [seen],
  );

  const latest = useRef({ share, othersHere });
  useEffect(() => {
    latest.current = { share, othersHere };
  });
  const send = useCallback(
    (block: string | null, kind: "look" | "select") => {
      // Clearing your place is always allowed; showing it only while sharing and someone is here.
      if (block !== null && (!latest.current.share || !latest.current.othersHere)) return;
      void api(`/v1/pages/${pageId}/focus`, { method: "POST", body: { block, kind } }).catch(() => {});
    },
    [pageId],
  );

  // Turning sharing off, or leaving, clears your outline for everyone.
  useEffect(() => {
    if (!share) send(null, "look");
  }, [share, send]);
  useEffect(() => () => send(null, "look"), [send]);

  return { peers, onEvent, send };
}

/** Reactions on parts of the page, live. Anyone who can comment may react; everyone can see them. */
export function useReactions(pageId: string, canReact: boolean) {
  const key = ["reactions", pageId];
  const list = useSWR(key, () => api<{ items: FrameReaction[] }>(`/v1/pages/${pageId}/reactions`), {
    shouldRetryOnError: false,
    revalidateOnFocus: false,
  });

  const react = useCallback(
    async (block: string, k: string, on: boolean) => {
      if (!canReact) return;
      // Show it at once, then let the server's answer settle the numbers.
      await list.mutate(
        async () => {
          await api(`/v1/pages/${pageId}/reactions`, { method: "PUT", body: { block, key: k, on } });
          return api<{ items: FrameReaction[] }>(`/v1/pages/${pageId}/reactions`);
        },
        {
          optimisticData: (current) => {
            const items = [...(current?.items ?? [])];
            const i = items.findIndex((r) => r.block === block && r.key === k);
            if (i === -1) {
              if (on) items.push({ block, key: k, count: 1, mine: true, who: [] });
            } else if (items[i].mine !== on) {
              const count = items[i].count + (on ? 1 : -1);
              if (count <= 0) items.splice(i, 1);
              else items[i] = { ...items[i], count, mine: on };
            }
            return { items };
          },
          rollbackOnError: true,
          revalidate: false,
        },
      );
    },
    [pageId, canReact, list],
  );

  const onEvent = useCallback(
    (e: LiveEvent) => {
      if (e.type === "reaction.changed") void list.mutate();
    },
    [list],
  );

  const items = useMemo(() => list.data?.items ?? NONE, [list.data]);
  return { items, react, onEvent };
}

/**
 * While the tab is hidden, counts things that happened and puts the count in the tab title, so a
 * background tab shows that something needs a look. It clears when the tab is shown again.
 */
export function useTabAlert(): () => void {
  const [count, setCount] = useState(0);
  const base = useRef("");

  useEffect(() => {
    const clear = () => {
      if (document.visibilityState === "visible") setCount(0);
    };
    document.addEventListener("visibilitychange", clear);
    return () => document.removeEventListener("visibilitychange", clear);
  }, []);

  useEffect(() => {
    if (count === 0) {
      if (base.current) document.title = base.current;
      base.current = "";
      return;
    }
    if (!base.current) base.current = document.title;
    document.title = `(${count}) ${base.current}`;
  }, [count]);

  useEffect(
    () => () => {
      if (base.current) document.title = base.current;
    },
    [],
  );

  return useCallback(() => {
    if (document.visibilityState === "hidden") setCount((c) => c + 1);
  }, []);
}
