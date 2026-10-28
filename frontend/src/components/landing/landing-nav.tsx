"use client";

import Link from "next/link";
import { motion, useScroll, useSpring } from "motion/react";
import { useEffect, useState } from "react";
import { Wordmark } from "@/components/brand";
import { LinkButton } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const sections = [
  { id: "loop", label: "The loop" },
  { id: "lane", label: "Pit lane" },
  { id: "history", label: "History" },
  { id: "safe", label: "Safety" },
  { id: "faq", label: "Questions" },
];

/** A dark bar with a numbered index. The number of the section you are in lights up. */
export function LandingNav() {
  const [active, setActive] = useState<string | null>(null);
  const { scrollYProgress } = useScroll();
  const bar = useSpring(scrollYProgress, { stiffness: 120, damping: 24 });

  useEffect(() => {
    const seen = new Map<string, number>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) seen.set(e.target.id, e.isIntersecting ? e.intersectionRatio : 0);
        const best = [...seen.entries()].sort((a, b) => b[1] - a[1])[0];
        setActive(best && best[1] > 0 ? best[0] : null);
      },
      { rootMargin: "-30% 0px -50% 0px", threshold: [0, 0.1, 0.5, 1] },
    );
    for (const s of sections) {
      const el = document.getElementById(s.id);
      if (el) io.observe(el);
    }
    return () => io.disconnect();
  }, []);

  return (
    <header className="on-band sticky top-0 z-30 border-b border-ink-line bg-ink text-ink-foreground">
      <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between gap-4 px-6">
        <Link href="/" aria-label="Paddock home">
          <Wordmark size={24} tone="band" />
        </Link>
        <nav aria-label="Sections" className="hidden items-center gap-1 md:flex">
          {sections.map((s, i) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              aria-current={active === s.id ? "location" : undefined}
              className={cn(
                "eyebrow flex h-8 items-center gap-2 rounded-full px-3 transition-colors duration-[120ms]",
                active === s.id ? "bg-white/10 text-ink-foreground" : "text-ink-muted hover:text-ink-foreground",
              )}
            >
              <span aria-hidden="true" className={active === s.id ? "text-signal" : undefined}>
                {String(i + 1).padStart(2, "0")}
              </span>
              {s.label}
            </a>
          ))}
        </nav>
        <nav aria-label="Account" className="flex items-center gap-1.5">
          <LinkButton href="/login" variant="ghost" className="text-ink-foreground hover:bg-white/10">
            Log in
          </LinkButton>
          <LinkButton href="/signup">Create account</LinkButton>
        </nav>
      </div>
      <motion.div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-[2px] origin-left bg-signal" style={{ scaleX: bar }} />
    </header>
  );
}
