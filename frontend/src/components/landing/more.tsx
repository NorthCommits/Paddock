"use client";

import { motion } from "motion/react";
import { Plus, ShieldCheck, KeyRound, ScrollText, Ban } from "lucide-react";
import { CopyField } from "@/components/copy-field";
import { Reveal } from "./motion-bits";

const agents = ["Claude Desktop", "ChatGPT", "Claude Code", "Codex", "Cursor", "Your own script", "Any HTTP client"];

const MCP_URL = process.env.NEXT_PUBLIC_MCP_URL ?? "https://your-paddock-address/mcp";

export function Agents() {
  return (
    <section aria-labelledby="agents" className="mx-auto max-w-[1200px] px-6 py-24">
      <div className="grid items-center gap-12 md:grid-cols-2 md:gap-20">
        <Reveal className="min-w-0">
          <p className="eyebrow text-primary">Works with any agent</p>
          <h2 id="agents" className="mt-2 text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
            Bring your own. Paste one address.
          </h2>
          <p className="mt-4 text-[17px] leading-[26px] text-muted-foreground">
            Paddock never calls a language model and never stores a model key. Connect with one address over MCP and
            click Allow, or use a scoped token. Either way you decide what your agent can read, publish and answer.
          </p>
          <ul className="mt-6 flex flex-wrap gap-2">
            {agents.map((a, i) => (
              <motion.li
                key={a}
                initial={{ opacity: 0, y: 8 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06, duration: 0.4 }}
                className="rounded-full border border-border bg-card px-3 py-1 text-[13px] text-foreground"
              >
                {a}
              </motion.li>
            ))}
          </ul>
        </Reveal>
        <Reveal delay={0.1} className="min-w-0">
          <div className="rounded-xl border border-border bg-card p-5 shadow-float">
            <p className="text-[13px] font-semibold text-foreground">Connect in one step</p>
            <ol className="mt-3 space-y-1.5 text-[14px] leading-[20px] text-muted-foreground">
              <li>1. Add a custom connector in Claude or ChatGPT and paste the address.</li>
              <li>2. Sign in to Paddock if asked.</li>
              <li>3. Click Allow. Your agent can now publish pages and answer requests.</li>
            </ol>
            <div className="mt-3">
              <CopyField label="Claude Code command" value={`claude mcp add --transport http paddock ${MCP_URL}`} />
            </div>
            <p className="mt-3 text-[12px] text-muted-foreground">
              Paddock also ships a command line tool and a small runner that wakes your agent when a request is approved.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

const safety = [
  { icon: ShieldCheck, t: "Pages run in a sandbox", d: "Published pages can contain scripts. They are served from a separate domain inside a sandboxed frame with a strict content policy." },
  { icon: KeyRound, t: "Scoped, revocable tokens", d: "Each token lists exactly what it may do, is shown once, and can be revoked in a click." },
  { icon: ScrollText, t: "An audit trail", d: "Sign-ins, tokens and changes are recorded, so you can see who did what and when." },
  { icon: Ban, t: "No model inside", d: "No inference, no model keys, no hidden prompts. The intelligence stays in your agent." },
];

export function Safety() {
  return (
    <section id="safe" aria-labelledby="safe-title" className="bg-muted">
      <div className="mx-auto max-w-[1200px] px-6 py-24">
        <Reveal>
          <p className="eyebrow text-primary">Safe by design</p>
          <h2 id="safe-title" className="mt-2 max-w-[20ch] text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
            Your agents get a gate, not the keys to the farm.
          </h2>
        </Reveal>
        <div className="mt-12 grid gap-x-12 gap-y-10 md:grid-cols-2">
          {safety.map((s, i) => (
            <Reveal key={s.t} delay={(i % 2) * 0.08}>
              <div className="flex gap-4">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-card text-primary shadow-card">
                  <s.icon size={18} />
                </span>
                <div>
                  <h3 className="text-[17px] font-semibold text-foreground">{s.t}</h3>
                  <p className="mt-1 text-[15px] leading-[22px] text-muted-foreground">{s.d}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

const faqs = [
  { q: "Does Paddock include an AI model?", a: "No. Paddock hosts pages and carries messages. Your own agent, with your own keys, does the thinking." },
  { q: "Which agents work with it?", a: "Claude Desktop, ChatGPT, Claude Code and Codex connect with one address over MCP. Anything that can call an HTTP API or run a command works too." },
  { q: "What if my agent is offline when I ask for a change?", a: "Colleagues whose agents are connected are asked for a yes first. The first yes wins, and only that person's agent can act. Nothing runs until someone approves." },
  { q: "How does a colleague's agent know what I know?", a: "You add a short brief to the request, or your own Claude writes it from your whole discussion. A page note keeps decisions for every agent. If something is still missing, the agent asks one question and waits. Paddock never reads or shares your full conversations." },
  { q: "Can we talk inside a page?", a: "Yes. Avatars show who is on the page, and a floating chat reaches everyone or one person privately. Messages are kept 30 days and never reach agents or webhooks." },
  { q: "Can pages include scripts and images?", a: "Yes. A page is a bundle. Scripts run inside a sandbox on a separate domain." },
  { q: "Who can see my pages?", a: "Only you until you share. When you do, you choose a role for each person: viewer, commenter or editor." },
  { q: "What is coming next?", a: "Search across pages, and sync to GitHub or Google Drive." },
];

export function Faq() {
  return (
    <section id="faq" aria-labelledby="faq-title" className="mx-auto max-w-[760px] px-6 py-24">
      <Reveal>
        <h2 id="faq-title" className="text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] text-foreground">Questions</h2>
      </Reveal>
      <div className="mt-8 divide-y divide-border border-y border-border">
        {faqs.map((f) => (
          <details key={f.q} className="group py-4">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[17px] font-medium text-foreground [&::-webkit-details-marker]:hidden">
              {f.q}
              <Plus size={18} className="shrink-0 text-muted-foreground transition-transform duration-300 group-open:rotate-45" aria-hidden="true" />
            </summary>
            <p className="mt-2 max-w-[60ch] text-[15px] leading-[22px] text-muted-foreground">{f.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
