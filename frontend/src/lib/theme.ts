"use client";

import { useCallback, useEffect } from "react";
import useSWR, { mutate } from "swr";
import { api } from "./api";
import type { Me } from "./api";

export type Theme = "system" | "light" | "dark";

// A copy of the signed-in person's choice, so the very first paint is already right. The account is
// the source of truth. The copy is dropped when the person signs out.
const KEY = "paddock-theme";

export function applyTheme(theme: Theme) {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {}
}

// Nobody is signed in, so follow the device.
export function forgetTheme() {
  applyTheme("system");
}

export function useTheme(): [Theme, (t: Theme) => void] {
  // Reads the signed-in person from the shared "me" data. With no fetcher it never makes a request,
  // so public pages stay free of calls.
  const { data: me } = useSWR<Me>("me", null);
  const theme: Theme = me?.user.theme ?? "system";

  useEffect(() => {
    if (me) applyTheme(theme);
  }, [me, theme]);

  const setTheme = useCallback(
    async (next: Theme) => {
      const previous = theme;
      const show = (value: Theme) => {
        applyTheme(value);
        return mutate<Me>("me", (cur) => cur && { ...cur, user: { ...cur.user, theme: value } }, { revalidate: false });
      };
      await show(next);
      try {
        await api("/v1/me", { method: "PATCH", body: { theme: next } });
      } catch {
        await show(previous); // could not save, so put the old choice back
      }
    },
    [theme],
  );

  return [theme, setTheme];
}
