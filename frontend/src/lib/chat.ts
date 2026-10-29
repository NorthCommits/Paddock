"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSWRConfig } from "swr";
import type { LiveEvent } from "./live";

/** The key of a conversation: "all" for the whole page, otherwise the other person's id. */
export const keyOf = (selected: string | null) => selected ?? "all";

/** Which chat is open, and how many unread messages each conversation has. */
export function useChat(pageId: string, meId: string) {
  const { mutate } = useSWRConfig();
  const [open, setOpen] = useState(false);
  const [minimised, setMinimised] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [unread, setUnread] = useState<Record<string, number>>({});

  // What the live handler needs to know without being recreated on every change.
  const now = useRef({ open, minimised, selected });
  useEffect(() => {
    now.current = { open, minimised, selected };
  });

  const watching = open && !minimised;
  const key = keyOf(selected);
  useEffect(() => {
    if (watching) setUnread((u) => (u[key] ? { ...u, [key]: 0 } : u));
  }, [watching, key]);

  const select = useCallback((id: string | null) => setSelected(id), []);

  const onEvent = useCallback(
    (e: LiveEvent | "resync") => {
      const refetch = (k: string) => mutate(["messages", pageId, k]);
      if (e === "resync") {
        void mutate((k) => Array.isArray(k) && k[0] === "messages" && k[1] === pageId);
        return;
      }
      if (!e.type.startsWith("message.")) return;
      const sender = String(e.data.sender_id);
      const to = e.data.to ? String(e.data.to) : null;
      const conversation = to === null ? "all" : sender === meId ? to : sender;
      void refetch(conversation);
      if (e.type === "message.created" && sender !== meId) {
        const { open: o, minimised: m, selected: s } = now.current;
        if (!(o && !m && keyOf(s) === conversation)) {
          setUnread((u) => ({ ...u, [conversation]: (u[conversation] ?? 0) + 1 }));
        }
      }
    },
    [mutate, pageId, meId],
  );

  const total = Object.values(unread).reduce((a, b) => a + b, 0);
  return { open, setOpen, minimised, setMinimised, selected, select, unread, total, onEvent };
}

export type Chat = ReturnType<typeof useChat>;
