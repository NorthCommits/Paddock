"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { FileText, KeyRound, LogOut, Moon, Palette as PaletteIcon, PlugZap, Plus, Shield, Sun, Upload, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { signOutNow } from "@/lib/auth/session";
import { useTheme } from "@/lib/theme";

function Row({ icon, children, onSelect }: { icon: ReactNode; children: ReactNode; onSelect: () => void }) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex h-9 cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-[13px] text-foreground transition-colors duration-[120ms] data-[selected=true]:bg-muted [&_svg]:size-4 [&_svg]:text-muted-foreground"
    >
      {icon}
      {children}
    </Command.Item>
  );
}

export function Palette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const [, setTheme] = useTheme();

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
    await signOutNow();
    router.push("/login");
  }

  const group = "[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-subtle";

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/35 backdrop-blur-[2px] duration-200 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <Dialog.Content
          aria-label="Command palette"
          className="fixed left-1/2 top-[14vh] z-50 w-[calc(100%-32px)] max-w-lg -translate-x-1/2 overflow-hidden rounded-xl bg-card shadow-float duration-200 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Dialog.Description className="sr-only">Search for a command and press enter.</Dialog.Description>
          <Command>
            <Command.Input
              placeholder="Type a command"
              className="h-12 w-full border-b border-border bg-transparent px-4 text-[15px] text-foreground outline-none placeholder:text-subtle"
            />
            <Command.List className="max-h-80 overflow-y-auto p-1.5">
              <Command.Empty className="px-3 py-6 text-[13px] text-muted-foreground">No matching command.</Command.Empty>
              <Command.Group heading="Go to" className={group}>
                <Row icon={<FileText />} onSelect={() => go("/pages")}>Pages</Row>
                <Row icon={<PlugZap />} onSelect={() => go("/connect")}>Connect an agent</Row>
                <Row icon={<UserRound />} onSelect={() => go("/settings/profile")}>Profile</Row>
                <Row icon={<PaletteIcon />} onSelect={() => go("/settings/appearance")}>Appearance</Row>
                <Row icon={<Shield />} onSelect={() => go("/settings/security")}>Security</Row>
                <Row icon={<KeyRound />} onSelect={() => go("/settings/tokens")}>Tokens</Row>
              </Command.Group>
              <Command.Group heading="Actions" className={group}>
                <Row icon={<Upload />} onSelect={() => go("/pages?new=1")}>Upload a page</Row>
                <Row icon={<Plus />} onSelect={() => go("/settings/tokens?new=1")}>Create a token</Row>
                <Row icon={<Sun />} onSelect={() => { setTheme("light"); setOpen(false); }}>Light theme</Row>
                <Row icon={<Moon />} onSelect={() => { setTheme("dark"); setOpen(false); }}>Dark theme</Row>
                <Row icon={<LogOut />} onSelect={signOut}>Sign out</Row>
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
