"use client";

import { AnimatePresence, motion } from "motion/react";
import { FileCode2, Image as ImageIcon, Folder } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { Reveal } from "./motion-bits";

const card =
  "group relative overflow-hidden rounded-xl border border-border bg-card p-6 shadow-card transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-float";

const events = ["comment.created", "request.opened", "version.published", "comment.created", "request.done"];

function LiveStream() {
  const [i, setI] = useState(3);
  useEffect(() => {
    const t = setInterval(() => setI((n) => n + 1), 1600);
    return () => clearInterval(t);
  }, []);
  const shown = [i - 2, i - 1, i];
  return (
    <div className="mt-5 space-y-1.5 font-mono text-[11px]" aria-hidden="true">
      <AnimatePresence initial={false} mode="popLayout">
        {shown.map((n) => (
          <motion.div
            key={n}
            layout
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: n === i ? 1 : 0.55, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.35, ease: [0.2, 0, 0, 1] }}
            className="flex items-center gap-2 rounded-md bg-muted px-2.5 py-1.5 text-foreground"
          >
            <span className="relative flex size-1.5">
              {n === i && <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60" />}
              <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
            </span>
            {events[((n % events.length) + events.length) % events.length]}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function VersionStack() {
  const layers = [
    { label: "v3", y: 0, s: 1 },
    { label: "v2", y: 14, s: 0.95 },
    { label: "v1", y: 28, s: 0.9 },
  ];
  return (
    <motion.div className="relative mt-5 h-[104px]" initial="rest" whileHover="fan" aria-hidden="true">
      {layers.map((l, i) => (
        <motion.div
          key={l.label}
          variants={{
            rest: { y: l.y, scale: l.s },
            fan: { y: l.y + i * 10, scale: l.s },
          }}
          transition={{ type: "spring", stiffness: 380, damping: 28 }}
          style={{ zIndex: 3 - i, top: 0 }}
          className={cn(
            "absolute inset-x-0 flex h-14 items-center justify-between rounded-lg border border-border px-3 text-[12px]",
            i === 0 ? "bg-card text-foreground" : "bg-muted text-muted-foreground",
          )}
        >
          <span className="font-medium tnum">{l.label}</span>
          <span className="text-[11px]">{i === 0 ? "Current" : "Kept"}</span>
        </motion.div>
      ))}
    </motion.div>
  );
}

function Bundle() {
  const files = [
    { n: "index.html", i: FileCode2 },
    { n: "chart.js", i: FileCode2 },
    { n: "cover.png", i: ImageIcon },
  ];
  return (
    <div className="mt-5 rounded-lg bg-muted p-3 font-mono text-[11px] text-foreground" aria-hidden="true">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Folder size={13} /> q3-revenue/
      </div>
      <ul className="mt-2 space-y-1.5 border-l border-border pl-3">
        {files.map((f, k) => (
          <motion.li
            key={f.n}
            className="flex items-center gap-2"
            initial={{ opacity: 0, x: -8 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 + k * 0.12, duration: 0.4, ease: [0.2, 0, 0, 1] }}
          >
            <f.i size={13} className="text-primary" /> {f.n}
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

function Roles() {
  const roles = ["Viewer", "Commenter", "Editor", "Owner"];
  return (
    <div className="mt-5 flex items-end gap-2" aria-hidden="true">
      {roles.map((r, k) => (
        <motion.div
          key={r}
          className="flex flex-1 flex-col justify-end rounded-md bg-primary-soft px-2 pb-2 pt-1 text-[11px] font-medium text-primary"
          initial={{ height: 0, opacity: 0 }}
          whileInView={{ height: 34 + k * 14, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 + k * 0.1, duration: 0.5, ease: [0.2, 0, 0, 1] }}
        >
          {r}
        </motion.div>
      ))}
    </div>
  );
}

export function Features() {
  const items = [
    { t: "Live, without polling", d: "Updates stream in as they happen. Agents listen over a stream or signed webhooks.", v: <LiveStream /> },
    { t: "Every version kept", d: "Compare, restore and discuss any earlier version of a page.", v: <VersionStack /> },
    { t: "Scripts and images welcome", d: "Pages are bundles. They run sandboxed on a separate domain.", v: <Bundle /> },
    { t: "Private by default", d: "Share with people by role, from viewer up to owner.", v: <Roles /> },
  ];
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {items.map((it, k) => (
        <Reveal key={it.t} delay={(k % 2) * 0.08}>
          <div className={card}>
            <h3 className="text-[17px] font-semibold text-foreground">{it.t}</h3>
            <p className="mt-1 max-w-[34ch] text-[15px] leading-[22px] text-muted-foreground">{it.d}</p>
            {it.v}
          </div>
        </Reveal>
      ))}
    </div>
  );
}
