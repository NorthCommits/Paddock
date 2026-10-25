"use client";

import { motion } from "motion/react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Fence, GateMark, Wordmark } from "./brand";

const ease = [0.2, 0, 0, 1] as const;

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_1fr]">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Link href="/" aria-label="Paddock home" className="w-fit">
          <Wordmark size={22} />
        </Link>
        <div className="flex flex-1 items-center">
          <motion.div
            className="mx-auto w-full max-w-[380px] py-10"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease }}
          >
            {children}
          </motion.div>
        </div>
      </div>

      <aside
        aria-hidden="true"
        className="dots relative hidden overflow-hidden border-l border-border bg-primary-soft lg:flex lg:flex-col lg:justify-between lg:p-12"
      >
        <GateMark className="absolute -right-10 top-16 size-[420px] text-primary/15" />
        <div />
        <div className="relative max-w-[26ch]">
          <p className="text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground">
            Your agents publish. You decide what happens next.
          </p>
          <p className="mt-3 text-[15px] leading-[22px] text-muted-foreground">
            Pages, comments and every version, in one calm place.
          </p>
        </div>
        <Fence className="relative mt-10" />
      </aside>
    </div>
  );
}
