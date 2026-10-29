"use client";

import { Check } from "lucide-react";
import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { CopyField } from "@/components/copy-field";
import { cn } from "@/lib/utils";
import { ConnectedBadge } from "./connected-badge";

type ToolId = "claude-desktop" | "chatgpt" | "claude-code" | "codex";

type Tool = {
  id: ToolId;
  label: string;
  /** What to copy, and what it is called on the copy button. */
  copy: (address: string) => { label: string; value: string };
  steps: (address: string) => string[];
  note: string;
};

const TOOLS: Tool[] = [
  {
    id: "claude-desktop",
    label: "Claude Desktop",
    copy: (a) => ({ label: "address", value: a }),
    steps: () => [
      "Open Settings, then Connectors, then Add custom connector.",
      "Paste the address below and choose Add.",
      "Choose Connect, sign in to Paddock if asked, and click Allow.",
    ],
    note: "Custom connectors depend on your Claude plan.",
  },
  {
    id: "chatgpt",
    label: "ChatGPT",
    copy: (a) => ({ label: "address", value: a }),
    steps: () => [
      "In ChatGPT, turn on Developer mode in Settings, then Connectors, then Advanced.",
      "Choose Create connector, paste the address below, and pick OAuth for sign-in.",
      "Sign in to Paddock if asked and click Allow.",
    ],
    note: "Developer mode is available on ChatGPT Pro and Plus plans.",
  },
  {
    id: "claude-code",
    label: "Claude Code",
    copy: (a) => ({ label: "Claude Code command", value: `claude mcp add --transport http paddock ${a}` }),
    steps: () => [
      "Paste the command below into your terminal and run it.",
      "Start Claude Code, type /mcp, and choose paddock.",
      "Choose Authenticate, sign in to Paddock if asked, and click Allow.",
    ],
    note: "Works with the Claude Code terminal app and its desktop app.",
  },
  {
    id: "codex",
    label: "Codex",
    copy: (a) => ({ label: "Codex command", value: `codex mcp add paddock --url ${a}` }),
    steps: () => [
      "Paste the command below into your terminal and run it.",
      "Codex opens your browser. Sign in to Paddock if asked.",
      "Click Allow, then return to Codex.",
    ],
    note: "Works with the Codex command line tool.",
  },
];

// A token's name starts with the app's name. The more specific name is checked first, so
// "Claude Code" is never taken for "Claude".
const PREFIXES: [string, ToolId][] = [
  ["claude code", "claude-code"],
  ["claude", "claude-desktop"],
  ["chatgpt", "chatgpt"],
  ["codex", "codex"],
];

export function matchTool(name: string): ToolId | null {
  const lower = name.trim().toLowerCase();
  return PREFIXES.find(([prefix]) => lower.startsWith(prefix))?.[1] ?? null;
}

export function ToolTabs({ mcpUrl, connectedNames }: { mcpUrl: string; connectedNames: string[] }) {
  const [active, setActive] = useState<ToolId>("claude-desktop");
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const connected = new Set(connectedNames.map(matchTool).filter((t): t is ToolId => t !== null));

  function onKey(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = TOOLS.length - 1;
    const next =
      e.key === "ArrowRight" ? (index === last ? 0 : index + 1)
      : e.key === "ArrowLeft" ? (index === 0 ? last : index - 1)
      : e.key === "Home" ? 0
      : e.key === "End" ? last
      : -1;
    if (next < 0) return;
    e.preventDefault();
    setActive(TOOLS[next].id);
    refs.current[TOOLS[next].id]?.focus();
  }

  const tool = TOOLS.find((t) => t.id === active) ?? TOOLS[0];
  const copy = tool.copy(mcpUrl);

  return (
    <div>
      <div role="tablist" aria-label="Choose your tool" className="flex flex-wrap gap-1 rounded-lg bg-card p-1 shadow-card">
        {TOOLS.map((t, i) => {
          const selected = t.id === active;
          return (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[t.id] = el;
              }}
              role="tab"
              id={`tool-tab-${t.id}`}
              aria-selected={selected}
              aria-controls="tool-panel"
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(t.id)}
              onKeyDown={(e) => onKey(e, i)}
              className={cn(
                "inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors duration-[120ms]",
                selected ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
              {connected.has(t.id) && (
                <>
                  <Check size={13} className="text-primary" aria-hidden="true" />
                  <span className="sr-only">(connected)</span>
                </>
              )}
            </button>
          );
        })}
      </div>

      <div id="tool-panel" role="tabpanel" aria-labelledby={`tool-tab-${tool.id}`} className="mt-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[15px] font-semibold text-foreground">Connect {tool.label}</h2>
          <ConnectedBadge connected={connected.has(tool.id)} />
        </div>
        <ol className="mt-3 space-y-2.5">
          {tool.steps(mcpUrl).map((text, i) => (
            <li key={text} className="flex gap-3 text-[14px] leading-[21px] text-foreground">
              <span className="tnum flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[12px] font-semibold text-primary">
                {i + 1}
              </span>
              <span className="pt-px">{text}</span>
            </li>
          ))}
        </ol>
        <div className="mt-4">
          <CopyField label={copy.label} value={copy.value} />
        </div>
        <p className="mt-2 text-[12px] text-muted-foreground">{tool.note}</p>
      </div>
    </div>
  );
}
