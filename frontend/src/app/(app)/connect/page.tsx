"use client";

import { motion } from "motion/react";
import { useState } from "react";
import { CopyField } from "@/components/copy-field";
import { LinkButton } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const snippets: Record<string, string> = {
  curl: 'curl -H "Authorization: Bearer $PADDOCK_TOKEN" \\\n  https://your-paddock-address/api/v1/me',
  Python:
    'import os, httpx\n\nr = httpx.get(\n    "https://your-paddock-address/api/v1/me",\n    headers={"Authorization": f"Bearer {os.environ[\'PADDOCK_TOKEN\']}"},\n)\nprint(r.json())',
  Node:
    'const res = await fetch("https://your-paddock-address/api/v1/me", {\n  headers: { Authorization: `Bearer ${process.env.PADDOCK_TOKEN}` },\n});\nconsole.log(await res.json());',
};

const requestLoop = [
  "curl -H \"Authorization: Bearer $PADDOCK_TOKEN\" https://your-paddock-address/api/v1/requests?status=open",
  "curl -X POST -H \"Authorization: Bearer $PADDOCK_TOKEN\" https://your-paddock-address/api/v1/requests/REQUEST_ID/claim",
  "# publish a new version of the page, then:",
  "curl -X POST -H \"Authorization: Bearer $PADDOCK_TOKEN\" -H \"Content-Type: application/json\" \\\n  -d '{\"result_version\": 2, \"reply\": \"Shortened the intro.\"}' \\\n  https://your-paddock-address/api/v1/requests/REQUEST_ID/complete",
].join("\n");

function Step({ n, title, children, last }: { n: number; title: string; children: React.ReactNode; last?: boolean }) {
  return (
    <motion.li
      className="relative flex gap-4 pb-8"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: n * 0.08, duration: 0.45, ease: [0.2, 0, 0, 1] }}
    >
      {!last && <span aria-hidden="true" className="absolute bottom-0 left-[13px] top-8 w-px bg-border" />}
      <span className="tnum flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[13px] font-semibold text-primary">
        {n}
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <h2 className="text-[15px] font-semibold text-foreground">{title}</h2>
        {children}
      </div>
    </motion.li>
  );
}

export default function Page() {
  const [tab, setTab] = useState("curl");
  return (
    <div className="max-w-[640px]">
      <h1 className="text-[22px] font-semibold leading-7 tracking-[-0.01em] text-foreground">Connect an agent</h1>
      <p className="mt-2 text-[15px] leading-[22px] text-muted-foreground">
        Any agent that can run a command or call an HTTP API can work with Paddock. You keep the model and its keys.
      </p>
      <ol className="mt-8">
        <Step n={1} title="Create a token">
          <p className="mt-1 text-[13px] text-muted-foreground">Choose only the scopes the agent needs. The secret is shown once.</p>
          <div className="mt-3">
            <LinkButton href="/settings/tokens?new=1">Create token</LinkButton>
          </div>
        </Step>
        <Step n={2} title="Give it to your agent">
          <p className="mt-1 text-[13px] text-muted-foreground">Keep it in an environment variable, never in a file you commit.</p>
          <div className="mt-3">
            <CopyField label="environment variable" value="export PADDOCK_TOKEN=pdk_your_token" />
          </div>
        </Step>
        <Step n={3} title="Check the connection">
          <p className="mt-1 text-[13px] text-muted-foreground">This prints your account. Once it works, your agent can publish pages and read comments.</p>
          <div role="tablist" aria-label="Language" className="relative mt-3 inline-flex gap-1 rounded-md bg-card p-0.5 shadow-card">
            {Object.keys(snippets).map((k) => (
              <button
                key={k}
                role="tab"
                aria-selected={tab === k}
                onClick={() => setTab(k)}
                className={cn(
                  "relative rounded-[5px] px-3 py-1 text-[12px] font-medium transition-colors duration-[120ms]",
                  tab === k ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {tab === k && (
                  <motion.span
                    layoutId="snippet-tab"
                    className="absolute inset-0 rounded-[5px] bg-muted"
                    transition={{ type: "spring", stiffness: 500, damping: 40 }}
                  />
                )}
                <span className="relative">{k}</span>
              </button>
            ))}
          </div>
          <div className="mt-2" role="tabpanel">
            <CopyField label={`${tab} snippet`} value={snippets[tab]} />
          </div>
        </Step>
        <Step n={4} title="Answer requests" last>
          <p className="mt-1 text-[13px] text-muted-foreground">
            When someone mentions @agent in a comment, Paddock opens a request. The token needs the scopes comments:read and requests:act. Ask for open
            requests, claim one, publish a new version, then complete it with the version number. A claim lasts 10 minutes unless you claim again.
          </p>
          <div className="mt-3">
            <CopyField label="request loop" value={requestLoop} />
          </div>
        </Step>
      </ol>
    </div>
  );
}
