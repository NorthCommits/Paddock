"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function CopyField({ value, label, wrap = false }: { value: string; label: string; wrap?: boolean }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div className="flex items-start gap-2 rounded-lg border border-border bg-muted p-2.5">
      <pre
        className={`min-w-0 flex-1 py-1 pl-1 font-mono text-[12px] leading-[18px] text-foreground ${
          wrap ? "whitespace-pre-wrap break-all" : "overflow-x-auto whitespace-pre"
        }`}
      >
        {value}
      </pre>
      <Button size="sm" variant="secondary" onClick={copy} aria-label={`Copy ${label}`}>
        {copied ? <Check className="text-primary" /> : <Copy />}
        <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
      </Button>
    </div>
  );
}
