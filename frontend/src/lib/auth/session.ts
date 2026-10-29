"use client";

import { mutate } from "swr";
import { forgetToken } from "@/lib/api";
import { forgetTheme } from "@/lib/theme";
import { authClient } from "./client";

// Neon's client reports problems as { error } instead of throwing. This turns one into text.
export function authMessage(error: { message?: string } | null | undefined): string {
  const text = error?.message?.trim();
  return text && text.length < 160 ? text : "Something went wrong. Try again.";
}

export function authCode(error: unknown): string {
  return String((error as { code?: string } | null)?.code ?? "");
}

// Called after signing in or out, so the next screen does not show the previous person.
export async function resetSessionCache() {
  forgetToken();
  await mutate(() => true, undefined, { revalidate: false });
}

export async function signOutNow() {
  await authClient.signOut().catch(() => undefined);
  await resetSessionCache();
  forgetTheme(); // signed out pages follow the device
}

// Only allow a path inside this site, so a crafted link cannot send people elsewhere.
export function safeNext(value: string | null): string | null {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : null;
}

// Keeps ?next= and ?email= when moving between the sign in screens.
export function carryQuery(next: string | null, email?: string | null): string {
  const q = new URLSearchParams();
  if (next) q.set("next", next);
  if (email) q.set("email", email);
  const text = q.toString();
  return text ? `?${text}` : "";
}
