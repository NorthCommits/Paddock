"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, setCsrf } from "@/lib/api";

export function Palette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (path: string) => {
    setOpen(false);
    router.push(path);
  };

  async function signOut() {
    setOpen(false);
    await api("/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    setCsrf(null);
    router.push("/login");
  }

  const item =
    "flex h-9 cursor-default items-center rounded-md px-2.5 text-[13px] text-ink data-[selected=true]:bg-grouped";

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="anim-fade fixed inset-0 bg-black/30" />
        <Dialog.Content
          aria-label="Command palette"
          className="anim-sheet fixed left-1/2 top-[14vh] w-[calc(100%-32px)] max-w-lg -translate-x-1/2 overflow-hidden rounded-lg bg-surface shadow-float"
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Command>
            <Command.Input
              placeholder="Type a command"
              className="h-12 w-full border-b border-line bg-transparent px-4 text-[15px] text-ink outline-none placeholder:text-ink-3"
            />
            <Command.List className="max-h-72 overflow-y-auto p-1.5">
              <Command.Empty className="px-3 py-6 text-[13px] text-ink-2">No matching command.</Command.Empty>
              <Command.Item className={item} onSelect={() => go("/pages")}>Go to pages</Command.Item>
              <Command.Item className={item} onSelect={() => go("/connect")}>Connect an agent</Command.Item>
              <Command.Item className={item} onSelect={() => go("/settings/tokens")}>Open tokens</Command.Item>
              <Command.Item className={item} onSelect={() => go("/settings/tokens?new=1")}>Create a token</Command.Item>
              <Command.Item className={item} onSelect={() => go("/settings/account")}>Open account</Command.Item>
              <Command.Item className={item} onSelect={signOut}>Sign out</Command.Item>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
