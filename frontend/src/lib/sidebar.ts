"use client";

import { useCallback, useEffect, useState } from "react";

const KEEP = "paddock-sidebar";
const SMALL_LAPTOP = 1280; // below this width the sidebar starts collapsed, unless the person chose

/**
 * Whether the desktop sidebar is the narrow icon rail. The person's choice is remembered in the
 * browser; without one, the rail is used on narrower screens. Cmd or Ctrl and B toggles it.
 */
export function useSidebarRail(): [boolean, () => void] {
  const [rail, setRail] = useState(false);

  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(KEEP);
    } catch {
      /* storage can be blocked */
    }
    setRail(saved ? saved === "rail" : window.innerWidth < SMALL_LAPTOP);
  }, []);

  const toggle = useCallback(() => {
    setRail((r) => {
      try {
        localStorage.setItem(KEEP, r ? "wide" : "rail");
      } catch {
        /* the choice just will not be remembered */
      }
      return !r;
    });
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key.toLowerCase() !== "b" || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(input|textarea|select)$/i.test(t.tagName))) return; // leave bold alone
      e.preventDefault();
      toggle();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  return [rail, toggle];
}
