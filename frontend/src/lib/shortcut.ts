"use client";

import { useEffect, useState } from "react";

// The key people press for the command search: Cmd on a Mac, Ctrl everywhere else. The server and the
// first paint cannot know the device, so they show Ctrl and a Mac switches to Cmd right after.
export function useModKey(): "Cmd" | "Ctrl" {
  const [key, setKey] = useState<"Cmd" | "Ctrl">("Ctrl");
  useEffect(() => {
    const nav = navigator as Navigator & { userAgentData?: { platform?: string } };
    const platform = nav.userAgentData?.platform || navigator.platform || "";
    if (/mac|iphone|ipad|ipod/i.test(platform)) setKey("Cmd");
  }, []);
  return key;
}
