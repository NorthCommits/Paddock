"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import type { Page } from "@/lib/api";

const MAX = 8000;

/** The page note: what anyone, or any agent, working on this page should know. Editors write it. */
export function ContextSheet({
  open,
  onOpenChange,
  page,
  canEdit,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  page: Page;
  canEdit: boolean;
  onSaved: () => void | Promise<void>;
}) {
  const [text, setText] = useState(page.context ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Start from the saved note each time the sheet opens, but never replace what is being typed.
  useEffect(() => {
    if (open) {
      setText(page.context ?? "");
      setError("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      await api(`/v1/pages/${page.id}/context`, { method: "PUT", body: { text } });
      await onSaved();
      onOpenChange(false);
    } catch (err) {
      setError((err as Error).message || "Could not save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      wide
      title="Page context"
      description="Decisions, constraints and terms for this page. Every agent that picks up a request reads it first."
    >
      {canEdit ? (
        <>
          <textarea
            aria-label="Page context"
            value={text}
            maxLength={MAX}
            rows={10}
            onChange={(e) => setText(e.target.value)}
            placeholder={"Audience: the board.\nDecision: keep the table, drop the chart.\nTerms: \"active\" means a sign in this month."}
            className="block w-full resize-y rounded-md border border-input-border bg-card px-3 py-2 text-[14px] leading-[1.5] text-foreground placeholder:text-muted-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25"
          />
          <div className="mt-1 flex items-center justify-between text-[12px] text-muted-foreground">
            <span>Agents add a dated line here when they finish a request.</span>
            <span className="tnum">{text.length} / {MAX}</span>
          </div>
          {error && <p role="alert" className="mt-2 text-[13px] text-destructive">{error}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button onClick={() => void save()} disabled={busy || text === (page.context ?? "")}>Save</Button>
          </div>
        </>
      ) : page.context ? (
        <p className="whitespace-pre-wrap break-words text-[14px] leading-[1.5] text-foreground">{page.context}</p>
      ) : (
        <p className="text-[14px] text-muted-foreground">Nothing has been written here yet.</p>
      )}
    </Sheet>
  );
}
