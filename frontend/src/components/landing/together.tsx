"use client";

import { MessageCircle, BookOpen } from "lucide-react";
import { initials, ringColor } from "@/lib/presence";
import { Reveal } from "./motion-bits";

const people = [
  { id: "maya", name: "Maya Rao" },
  { id: "dev", name: "Dev Shah" },
  { id: "nina", name: "Nina Park" },
];

function Avatar({ id, name }: { id: string; name: string }) {
  return (
    <span
      style={{ backgroundColor: ringColor(id) }}
      className="flex size-7 items-center justify-center rounded-full text-[11px] font-semibold text-white ring-2 ring-card"
      title={name}
    >
      {initials({ display_name: name, handle: id })}
    </span>
  );
}

function HerePanel() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-float">
      <div className="flex items-center justify-between">
        <p className="text-[15px] font-semibold text-foreground">Launch plan</p>
        <div className="flex -space-x-1.5" role="group" aria-label="Three people here now">
          {people.map((p) => (
            <Avatar key={p.id} {...p} />
          ))}
        </div>
      </div>
      <div className="mt-4 space-y-2" aria-hidden="true">
        <div className="h-2 w-4/5 rounded-full bg-border" />
        <div className="h-2 w-full rounded-full bg-border" />
        <div className="h-2 w-3/5 rounded-full bg-border" />
      </div>
      <div className="mt-5 rounded-xl border border-border bg-background p-3">
        <div className="flex gap-1.5">
          <span className="rounded-full border border-border px-2.5 py-1 text-[12px] text-foreground">Everyone</span>
          <span className="rounded-full border border-foreground bg-foreground px-2.5 py-1 text-[12px] text-background">Dev Shah</span>
        </div>
        <div className="mt-3 space-y-2 text-[13px] leading-[19px]">
          <p className="max-w-[85%] rounded-lg bg-muted px-2.5 py-1.5 text-foreground">Can you check the second email before I ask the agent?</p>
          <p className="ml-auto max-w-[85%] rounded-lg bg-foreground px-2.5 py-1.5 text-background">Looking now. Only you and I can see this.</p>
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <span className="relative flex size-11 items-center justify-center rounded-full bg-foreground text-background shadow-float">
          <MessageCircle size={19} aria-hidden="true" />
          <span aria-hidden="true" className="tnum absolute -right-1 -top-1 flex min-w-5 items-center justify-center rounded-full bg-signal px-1 text-[11px] font-bold leading-5 text-signal-foreground ring-2 ring-card">2</span>
        </span>
      </div>
    </div>
  );
}

function ContextPanel() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-float">
      <div className="flex items-start gap-2.5">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[11px] font-semibold text-primary">M</span>
        <div className="rounded-lg rounded-tl-sm bg-muted px-3 py-2 text-[13px] leading-[19px] text-foreground">
          <span className="font-medium text-primary">@agent</span> shorten the second email
        </div>
      </div>
      <div className="mt-2.5 rounded-md border border-border bg-muted px-2.5 py-2">
        <p className="text-[12px] font-medium text-muted-foreground">Context for the agent</p>
        <p className="mt-0.5 text-[13px] leading-[19px] text-foreground">Two lines, formal tone. The board reads this on Monday. Keep the pricing sentence.</p>
      </div>
      <div className="mt-2.5 flex items-start gap-2.5 pl-8">
        <div className="rounded-lg rounded-tl-sm border border-border px-3 py-2 text-[13px] leading-[19px] text-foreground">
          Dev&apos;s agent asks: should the discount line stay?
        </div>
      </div>
      <div className="mt-2.5 flex items-start gap-2.5">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[11px] font-semibold text-primary">M</span>
        <div className="rounded-lg rounded-tl-sm bg-muted px-3 py-2 text-[13px] leading-[19px] text-foreground">Yes, keep it.</div>
      </div>
      <div className="mt-4 flex items-center gap-2 rounded-md bg-primary-soft px-2.5 py-2 text-[12px] text-primary">
        <BookOpen size={14} aria-hidden="true" />
        <span>Page note updated: discount line stays, board audience.</span>
      </div>
    </div>
  );
}

export function Together() {
  return (
    <section id="together" aria-labelledby="together-title" className="mx-auto max-w-[1200px] px-6 py-24">
      <Reveal>
        <p className="eyebrow text-primary">People and agents, together</p>
        <h2 id="together-title" className="mt-2 max-w-[22ch] text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
          See who is here. Hand your agent the whole story.
        </h2>
      </Reveal>
      <div className="mt-12 grid gap-12 md:grid-cols-2 md:gap-16">
        <Reveal className="min-w-0">
          <HerePanel />
          <h3 className="mt-6 text-[19px] font-semibold text-foreground">Avatars and a chat bubble, not another column</h3>
          <p className="mt-2 text-[15px] leading-[22px] text-muted-foreground">
            Avatars show who has the page open right now, like a shared spreadsheet. A small floating chat talks to everyone on the page,
            or privately to one person. It sits over the page, so there is no second sidebar next to the comments. Unread messages show as a number.
          </p>
        </Reveal>
        <Reveal delay={0.1} className="min-w-0">
          <ContextPanel />
          <h3 className="mt-6 text-[19px] font-semibold text-foreground">A colleague&apos;s agent knows what you know</h3>
          <p className="mt-2 text-[15px] leading-[22px] text-muted-foreground">
            Add a short brief when you ask for a change, or have your own Claude write it from your whole discussion. A page note keeps
            decisions and constraints for every agent. If an agent still lacks something, it asks you one question and waits, instead of guessing.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
