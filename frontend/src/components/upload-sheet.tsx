"use client";

import { FilePlus2, FolderUp, X } from "lucide-react";
import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { ApiError, api } from "@/lib/api";
import type { Publish } from "@/lib/api";
import { bytes } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "./ui/button";
import { Sheet } from "./ui/dialog";
import { Field } from "./ui/input";

type Item = { path: string; file: File };

// Folder picks arrive as "folder/sub/file.css". Drop the outer folder name.
function toItem(file: File): Item {
  const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
  const path = rel ? rel.split("/").slice(1).join("/") : file.name;
  return { path: path || file.name, file };
}

export function UploadSheet({
  open,
  onClose,
  onDone,
  pageId,
  pageTitle,
}: {
  open: boolean;
  onClose: () => void;
  onDone: (result: Publish) => void | Promise<void>;
  pageId?: string; // set to publish a new version instead of a new page
  pageTitle?: string;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);
  const filesRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  const total = items.reduce((n, i) => n + i.file.size, 0);

  function add(list: FileList | null) {
    if (!list) return;
    const next = [...items];
    for (const f of Array.from(list)) {
      const item = toItem(f);
      const at = next.findIndex((n) => n.path === item.path);
      if (at >= 0) next[at] = item;
      else next.push(item);
    }
    setItems(next);
    setError("");
    if (!pageId && !title.trim() && next.length) {
      const rel = (list[0] as File & { webkitRelativePath?: string }).webkitRelativePath;
      const first = next.find((n) => /\.html?$/i.test(n.path)) ?? next[0];
      const base = rel ? rel.split("/")[0] : first.path.replace(/\.[^.]+$/, "");
      setTitle(base.replace(/[-_]+/g, " ").replace(/^./, (c) => c.toUpperCase()));
    }
  }

  function reset() {
    setItems([]);
    setTitle("");
    setMessage("");
    setError("");
  }

  function close() {
    reset();
    onClose();
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    add(e.dataTransfer.files);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!pageId && !title.trim()) return setError("Give the page a title.");
    if (items.length === 0) return setError("Add at least one file. An HTML file is the entry page.");
    setBusy(true);
    setError("");
    const form = new FormData();
    if (!pageId) form.append("title", title.trim());
    if (message.trim()) form.append("message", message.trim());
    for (const i of items) form.append("files", i.file, i.path);
    try {
      const result = await api<Publish>(pageId ? `/v1/pages/${pageId}/versions` : "/v1/pages", {
        method: "POST",
        form,
      });
      reset();
      await onDone(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      open={open}
      onOpenChange={(o) => !o && close()}
      title={pageId ? "Publish a new version" : "New page"}
      description={
        pageId
          ? `Upload files for ${pageTitle ?? "this page"}. Identical files do not create a new version.`
          : "Upload an HTML file, or a folder with an index.html and its assets."
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        {!pageId && (
          <Field id="page-title" label="Title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Q3 revenue report" />
        )}

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-6 text-center transition-colors duration-[120ms]",
            over ? "border-primary bg-primary-soft" : "border-border bg-muted/50",
          )}
        >
          <p className="text-[13px] text-muted-foreground">Drop files here, or choose</p>
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="secondary" onClick={() => filesRef.current?.click()}>
              <FilePlus2 aria-hidden="true" /> Files
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={() => folderRef.current?.click()}>
              <FolderUp aria-hidden="true" /> Folder
            </Button>
          </div>
          <input ref={filesRef} type="file" multiple hidden aria-label="Choose files" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
          <input
            ref={folderRef}
            type="file"
            hidden
            aria-label="Choose a folder"
            {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
            onChange={(e) => { add(e.target.files); e.target.value = ""; }}
          />
        </div>

        {items.length > 0 && (
          <div>
            <p className="tnum mb-1 text-[12px] text-muted-foreground">
              {items.length} {items.length === 1 ? "file" : "files"}, {bytes(total)}
            </p>
            <ul className="max-h-40 divide-y divide-border overflow-y-auto rounded-md border border-border">
              {items.map((i) => (
                <li key={i.path} className="flex items-center gap-2 px-2.5 py-1.5">
                  <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-foreground">{i.path}</span>
                  <span className="tnum text-[12px] text-subtle">{bytes(i.file.size)}</span>
                  <button
                    type="button"
                    aria-label={`Remove ${i.path}`}
                    onClick={() => setItems(items.filter((n) => n.path !== i.path))}
                    className="flex size-6 items-center justify-center rounded-sm text-muted-foreground hover:bg-muted"
                  >
                    <X size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <Field id="page-message" label="Note (optional)" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="What changed" maxLength={500} />

        {error && <p role="alert" className="text-[13px] text-destructive">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={close}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Publishing" : "Publish"}</Button>
        </div>
      </form>
    </Sheet>
  );
}
