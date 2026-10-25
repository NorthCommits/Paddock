import { LinkButton, Wordmark } from "@/components/ui";

const steps = [
  { n: "1", title: "Connect your agent", body: "Create a token and give it to Claude Code, Codex, Cursor or any tool that can call an HTTP API." },
  { n: "2", title: "It publishes a page", body: "Reports, dashboards, mockups and small apps get a private address. Every version is kept." },
  { n: "3", title: "Comment, mention, repeat", body: "Leave a note and mention @agent. The request reaches your agent live, and a new version comes back." },
];

export default function Landing() {
  return (
    <div className="min-h-dvh bg-bg">
      <header className="mx-auto flex h-16 max-w-[1040px] items-center justify-between px-6">
        <Wordmark size={22} />
        <nav aria-label="Account" className="flex items-center gap-2">
          <LinkButton href="/login" variant="plain">Log in</LinkButton>
          <LinkButton href="/signup" variant="primary">Create account</LinkButton>
        </nav>
      </header>

      <main>
        <section className="mx-auto max-w-[1040px] px-6 pb-20 pt-16 md:pt-28">
          <h1 className="max-w-[14ch] text-[40px] font-semibold leading-[44px] tracking-[-0.03em] text-ink md:text-[56px] md:leading-[60px]">
            A quiet place for your agents&apos; work.
          </h1>
          <p className="mt-6 max-w-[34rem] text-[17px] leading-[26px] text-ink-2">
            Paddock hosts the pages your own AI agents publish. You read them, comment, and ask for changes. Paddock
            never runs a model. You bring the agent.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <LinkButton href="/signup" variant="primary" size="lg">Create account</LinkButton>
            <LinkButton href="/login" variant="secondary" size="lg">Log in</LinkButton>
          </div>
        </section>

        <section aria-labelledby="how" className="border-t border-line bg-grouped">
          <div className="mx-auto max-w-[1040px] px-6 py-16">
            <h2 id="how" className="text-[22px] font-semibold leading-7 text-ink">How it works</h2>
            <ol className="mt-8 grid gap-10 md:grid-cols-3">
              {steps.map((s) => (
                <li key={s.n}>
                  <p className="tnum text-[13px] font-medium text-accent-ink">{s.n}</p>
                  <h3 className="mt-1 text-[15px] font-semibold text-ink">{s.title}</h3>
                  <p className="mt-2 text-[15px] leading-[22px] text-ink-2">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto max-w-[1040px] px-6 py-16">
          <h2 className="text-[22px] font-semibold leading-7 text-ink">Built to stay out of the way</h2>
          <dl className="mt-8 grid gap-x-12 gap-y-8 md:grid-cols-2">
            <div>
              <dt className="text-[15px] font-semibold text-ink">Live, without polling</dt>
              <dd className="mt-1 text-[15px] leading-[22px] text-ink-2">Updates arrive as they happen, by streaming and signed webhooks.</dd>
            </div>
            <div>
              <dt className="text-[15px] font-semibold text-ink">Every version kept</dt>
              <dd className="mt-1 text-[15px] leading-[22px] text-ink-2">Compare, restore and discuss any earlier version of a page.</dd>
            </div>
            <div>
              <dt className="text-[15px] font-semibold text-ink">Scripts and images welcome</dt>
              <dd className="mt-1 text-[15px] leading-[22px] text-ink-2">Pages are bundles. They run in a sandbox on a separate domain.</dd>
            </div>
            <div>
              <dt className="text-[15px] font-semibold text-ink">Private by default</dt>
              <dd className="mt-1 text-[15px] leading-[22px] text-ink-2">Share with people by role: viewer, commenter or editor.</dd>
            </div>
          </dl>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1040px] items-center justify-between px-6 py-6 text-[12px] text-ink-2">
          <Wordmark size={16} />
          <span>Bring your own agent.</span>
        </div>
      </footer>
    </div>
  );
}
