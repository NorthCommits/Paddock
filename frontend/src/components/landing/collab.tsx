"use client";

import { AnimatePresence, motion } from "motion/react";
import { Heart, MessageSquarePlus, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Reveal } from "./motion-bits";

const lines = [
  { t: "Launch moves to the second week of March.", c: { who: "Maya", text: "Can we confirm this with design first?" } },
  { t: "Pricing stays flat for existing customers.", c: { who: "Dev", text: "Agreed. Add the reasoning here." } },
  { t: "Onboarding emails go out in three steps.", c: { who: "Maya", text: "@agent shorten the second email" } },
  { t: "Support hours extend to weekends in April.", c: { who: "Dev", text: "Looks good to me." } },
];

export function Collab() {
  const [open, setOpen] = useState<number | null>(2);
  const [likes, setLikes] = useState({ up: 4, heart: 2, mineUp: false, mineHeart: false });

  return (
    <section aria-labelledby="collab" className="bg-muted">
      <div className="mx-auto grid max-w-[1120px] items-center gap-12 px-6 py-24 md:grid-cols-[420px_1fr] md:gap-20">
        <Reveal className="min-w-0">
          <p className="text-[13px] font-medium text-primary">Collaborate</p>
          <h2 id="collab" className="mt-2 text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
            Comment, then mention your agent.
          </h2>
          <p className="mt-4 text-[17px] leading-[26px] text-muted-foreground">
            Leave a note on a page, reply in threads, and mention <span className="font-medium text-foreground">@agent</span> to ask
            for a change. Your agent picks up the request, publishes a new version and replies in the thread.
          </p>
          <p className="mt-4 text-[13px] text-muted-foreground">Click a line in the page to try it.</p>
        </Reveal>

        <Reveal delay={0.1} className="min-w-0">
          <div className="rounded-xl border border-border bg-card p-6 shadow-float">
            <div className="flex items-center justify-between">
              <p className="text-[15px] font-semibold text-foreground">Launch plan</p>
              <span className="tnum rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-medium text-primary">v4</span>
            </div>
            <ul className="mt-4 space-y-1">
              {lines.map((l, i) => (
                <li key={l.t}>
                  <button
                    onClick={() => setOpen(open === i ? null : i)}
                    aria-expanded={open === i}
                    className={cn(
                      "group flex w-full items-start gap-2 rounded-md px-2 py-2 text-left text-[15px] leading-[22px] text-foreground transition-colors duration-[120ms]",
                      open === i ? "bg-primary-soft" : "hover:bg-muted",
                    )}
                  >
                    <MessageSquarePlus size={15} className={cn("mt-1 shrink-0 transition-opacity duration-[120ms]", open === i ? "text-primary opacity-100" : "text-subtle opacity-0 group-hover:opacity-100")} aria-hidden="true" />
                    {l.t}
                  </button>
                  <AnimatePresence initial={false}>
                    {open === i && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: [0.2, 0, 0, 1] }}
                        className="overflow-hidden"
                      >
                        <div className="ml-8 mt-1.5 flex items-start gap-2 pb-2">
                          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[11px] font-semibold text-primary">{l.c.who[0]}</span>
                          <div className="rounded-lg rounded-tl-sm bg-muted px-3 py-2 text-[13px] leading-[18px] text-foreground">
                            <span className="font-medium">{l.c.who}</span>
                            <br />
                            {l.c.text.startsWith("@agent") ? (
                              <>
                                <span className="font-medium text-primary">@agent</span>
                                {l.c.text.slice(6)}
                              </>
                            ) : (
                              l.c.text
                            )}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex items-center gap-2 border-t border-border pt-4">
              <button
                onClick={() => setLikes((s) => ({ ...s, up: s.up + (s.mineUp ? -1 : 1), mineUp: !s.mineUp }))}
                aria-pressed={likes.mineUp}
                className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] transition-[background-color,transform] duration-[120ms] active:scale-95", likes.mineUp ? "border-primary bg-primary-soft text-primary" : "border-border text-muted-foreground hover:bg-muted")}
              >
                <ThumbsUp size={13} /> <span className="tnum">{likes.up}</span>
              </button>
              <button
                onClick={() => setLikes((s) => ({ ...s, heart: s.heart + (s.mineHeart ? -1 : 1), mineHeart: !s.mineHeart }))}
                aria-pressed={likes.mineHeart}
                className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] transition-[background-color,transform] duration-[120ms] active:scale-95", likes.mineHeart ? "border-primary bg-primary-soft text-primary" : "border-border text-muted-foreground hover:bg-muted")}
              >
                <Heart size={13} /> <span className="tnum">{likes.heart}</span>
              </button>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
