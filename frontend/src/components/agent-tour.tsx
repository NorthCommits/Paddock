"use client";

import { Bot, Check, CheckCircle2, Copy, History, MessageSquarePlus, Plus, Send, Users } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import type { ReactNode } from "react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useCalm } from "@/lib/motion";

const FIRST_PROMPT = "Make a one page launch plan with milestones and a team section, and publish it to Paddock.";
const CHECK_PROMPT = "Check Paddock for open requests on my pages and handle them.";

const SEEN_KEY = "paddock-tour-seen";

export function tourSeen(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

export function markTourSeen() {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    // Remembering is a convenience only.
  }
}

function CopyPrompt({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1800);
        } catch {
          // Clipboard blocked. The text is still on screen to copy by hand.
        }
      }}
      className="group mt-3 flex w-full items-start gap-2 rounded-lg border border-border bg-muted px-3 py-2 text-left text-[13px] leading-[1.45] text-foreground transition-colors duration-[120ms] hover:border-primary/50"
    >
      <span className="min-w-0 flex-1">&ldquo;{text}&rdquo;</span>
      <span className="mt-0.5 shrink-0 text-muted-foreground group-hover:text-primary" aria-live="polite">
        {done ? <Check size={14} aria-label="Copied" /> : <Copy size={14} aria-label="Copy this prompt" />}
      </span>
    </button>
  );
}

// ------------------------------------------------------------ small pictures, drawn with the app's own tokens

function Frame({ children }: { children: ReactNode }) {
  return (
    <div aria-hidden="true" className="relative flex h-36 items-center justify-center overflow-hidden rounded-lg border border-border bg-muted p-4">
      {children}
    </div>
  );
}

function Line({ w, strong }: { w: string; strong?: boolean }) {
  return <span className={`block h-1.5 rounded-full ${strong ? "bg-foreground/70" : "bg-foreground/20"}`} style={{ width: w }} />;
}

function PublishArt() {
  return (
    <Frame>
      <div className="flex w-full items-center gap-3">
        <div className="flex-1 space-y-2">
          <div className="ml-auto w-[88%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-[11px] leading-[1.35] text-primary-foreground">
            Make a launch plan and publish it
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Bot size={12} /> Published, v1
          </div>
        </div>
        <div className="w-20 shrink-0 space-y-1.5 rounded-md border border-border bg-card p-2 shadow-card">
          <Line w="70%" strong />
          <Line w="100%" />
          <Line w="85%" />
          <Line w="60%" />
        </div>
      </div>
    </Frame>
  );
}

function OpenArt() {
  return (
    <Frame>
      <div className="w-full max-w-[220px] overflow-hidden rounded-md border border-border bg-card shadow-card">
        <div className="flex items-center gap-1.5 border-b border-border px-2 py-1.5">
          <span className="size-1.5 rounded-full bg-foreground/25" />
          <span className="size-1.5 rounded-full bg-foreground/25" />
          <span className="ml-1 text-[10px] font-medium text-foreground">Launch plan</span>
          <span className="ml-auto rounded bg-primary-soft px-1 text-[9px] font-semibold text-primary">v1</span>
        </div>
        <div className="space-y-1.5 p-2.5">
          <Line w="55%" strong />
          <Line w="100%" />
          <Line w="90%" />
          <Line w="40%" strong />
          <Line w="95%" />
        </div>
      </div>
    </Frame>
  );
}

function PointArt() {
  return (
    <Frame>
      <div className="relative w-full max-w-[230px] rounded-md border border-border bg-card p-3 shadow-card">
        <Line w="45%" strong />
        <div className="relative mt-2.5 rounded border-2 border-dashed border-primary/60 bg-primary/5 p-1.5">
          <span className="text-[11px] font-semibold text-foreground">Milestones</span>
          <span className="absolute -left-4 top-1/2 flex size-5 -translate-y-1/2 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-card">
            <Plus size={12} />
          </span>
        </div>
        <div className="mt-2.5 space-y-1.5">
          <Line w="100%" />
          <Line w="80%" />
        </div>
      </div>
    </Frame>
  );
}

function AskArt() {
  return (
    <Frame>
      <div className="w-full max-w-[240px] space-y-2">
        <div className="rounded-lg border border-border bg-card p-2.5 shadow-card">
          <div className="mb-1 rounded bg-muted px-1.5 py-1 text-[10px] text-muted-foreground">&ldquo;Milestones&rdquo;</div>
          <p className="text-[11px] leading-[1.4] text-foreground">
            Make this bolder,{" "}
            <span className="rounded bg-primary-soft px-1 py-0.5 font-semibold text-primary ring-1 ring-primary/30">@agent</span>
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="rounded-full bg-primary-soft px-2 py-0.5 text-[10px] font-medium text-primary">Waiting for agent</span>
          <Send size={11} className="text-muted-foreground" />
        </div>
      </div>
    </Frame>
  );
}

function ReviewArt() {
  return (
    <Frame>
      <div className="w-full max-w-[220px] space-y-1.5">
        {[
          { v: "v3", note: "Bolder milestones", on: true },
          { v: "v2", note: "Added team section", on: false },
          { v: "v1", note: "First version", on: false },
        ].map((r) => (
          <div key={r.v} className={`flex items-center gap-2 rounded-md border px-2 py-1.5 text-[11px] ${r.on ? "border-primary/50 bg-card shadow-card" : "border-border bg-card/60"}`}>
            <span className="font-semibold text-foreground">{r.v}</span>
            <span className="truncate text-muted-foreground">{r.note}</span>
            {r.on && <span className="ml-auto rounded bg-primary-soft px-1 text-[9px] font-semibold text-primary">Latest</span>}
          </div>
        ))}
      </div>
    </Frame>
  );
}

function TeamArt() {
  return (
    <Frame>
      <div className="w-full max-w-[240px] space-y-2">
        {[
          { who: "Musadiq", text: "Can we shorten this? @agent" },
          { who: "Swapnil's Claude", text: "Done, see v4.", agent: true },
        ].map((m) => (
          <div key={m.who} className="rounded-lg border border-border bg-card px-2.5 py-1.5 shadow-card">
            <p className="flex items-center gap-1 text-[10px] font-semibold text-foreground">
              {m.agent && <Bot size={10} />}
              {m.who}
            </p>
            <p className="text-[11px] text-muted-foreground">{m.text}</p>
          </div>
        ))}
      </div>
    </Frame>
  );
}

// ------------------------------------------------------------ the tour

const STEPS: { title: string; body: string; art: ReactNode; icon: ReactNode; prompt?: string }[] = [
  {
    title: "Ask your agent to publish a page",
    body: "In your agent's chat, describe what you want. It writes the page and publishes it here. You keep your own model and keys.",
    art: <PublishArt />,
    icon: <Send size={14} />,
    prompt: FIRST_PROMPT,
  },
  {
    title: "Open it in Paddock",
    body: "It appears under Pages straight away, with every version kept. Share it by link or invite people by email.",
    art: <OpenArt />,
    icon: <CheckCircle2 size={14} />,
  },
  {
    title: "Point at the exact part you mean",
    body: "Hover any heading, paragraph or image and press the + button, or select some text. The comment is attached to that spot.",
    art: <PointArt />,
    icon: <Plus size={14} />,
  },
  {
    title: "Mention @agent to ask for a change",
    body: "Agents only act when asked, so tell yours to look. You can also mention it in a reply to ask for another round.",
    art: <AskArt />,
    icon: <MessageSquarePlus size={14} />,
    prompt: CHECK_PROMPT,
  },
  {
    title: "Review, compare, go back any time",
    body: "Each change is a new version and only the changed parts update on screen. Open History to view or restore an older one.",
    art: <ReviewArt />,
    icon: <History size={14} />,
  },
  {
    title: "Bring your team",
    body: "Colleagues comment on the same page and each agent is named after its owner, like Musadiq's Codex. We email you when someone is waiting on your agent.",
    art: <TeamArt />,
    icon: <Users size={14} />,
  },
];

export function AgentTour({ apps, onDone }: { apps: string[]; onDone: () => void }) {
  const calm = useCalm();
  const names = apps.map((a) => a.replace(/ \(connected with sign-in\)$/, ""));

  return (
    <section aria-labelledby="tour-title" className="mb-10 overflow-hidden rounded-2xl border border-border bg-card shadow-card">
      <div className="flex flex-wrap items-center gap-4 border-b border-border bg-primary-soft px-5 py-5">
        <motion.span
          initial={calm ? false : { scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 18 }}
          className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground"
        >
          <CheckCircle2 size={22} aria-hidden="true" />
        </motion.span>
        <div className="min-w-0 flex-1">
          <h2 id="tour-title" className="text-[18px] font-semibold leading-6 tracking-[-0.01em] text-foreground">
            {names.length ? `${names.join(" and ")} is connected` : "Your agent is connected"}
          </h2>
          <p className="mt-0.5 text-[14px] leading-[20px] text-foreground/80">Here is how pages work, in six short steps.</p>
        </div>
      </div>

      <ol className="grid gap-4 p-5 md:grid-cols-2">
        {STEPS.map((s, i) => (
          <motion.li
            key={s.title}
            initial={calm ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: calm ? 0 : 0.08 * i, duration: 0.4, ease: [0.32, 0.72, 0, 1] }}
            className="rounded-xl border border-border bg-background p-3.5"
          >
            {s.art}
            <div className="mt-3 flex items-start gap-2.5">
              <span className="tnum flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-[12px] font-semibold text-primary-foreground">{i + 1}</span>
              <div className="min-w-0">
                <h3 className="text-[15px] font-semibold leading-5 text-foreground">{s.title}</h3>
                <p className="mt-1 text-[14px] leading-[1.5] text-muted-foreground">{s.body}</p>
              </div>
            </div>
            {s.prompt && <CopyPrompt text={s.prompt} />}
          </motion.li>
        ))}
      </ol>

      <div className="flex flex-wrap items-center gap-2 border-t border-border px-5 py-4">
        <Link
          href="/pages"
          onClick={onDone}
          className="inline-flex h-9 items-center rounded-md bg-signal px-4 text-[14px] font-semibold text-signal-foreground transition-colors hover:bg-signal-hover focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/40"
        >
          Go to my pages
        </Link>
        <Button variant="ghost" onClick={onDone}>Got it</Button>
      </div>
    </section>
  );
}
