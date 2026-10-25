import { Fence, GateMark, Wordmark } from "@/components/brand";
import { LinkButton } from "@/components/ui/button";
import { Features } from "@/components/landing/features";
import { HeroDemo } from "@/components/landing/hero-demo";
import { Reveal, RiseWords } from "@/components/landing/motion-bits";

const steps = [
  { n: "01", title: "Connect your agent", body: "Create a token and hand it to Claude Code, Codex, Cursor or any tool that can call an HTTP API." },
  { n: "02", title: "It publishes a page", body: "Reports, dashboards, mockups and small apps get a private address. Every version is kept." },
  { n: "03", title: "Comment, mention, repeat", body: "Leave a note and mention @agent. The request reaches your agent live, and a new version comes back." },
];

export default function Landing() {
  return (
    <div className="min-h-dvh bg-background">
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1120px] items-center justify-between px-6">
          <Wordmark size={24} />
          <nav aria-label="Account" className="flex items-center gap-1.5">
            <LinkButton href="/login" variant="ghost">Log in</LinkButton>
            <LinkButton href="/signup">Create account</LinkButton>
          </nav>
        </div>
      </header>

      <main>
        <section className="dots relative">
          <div className="mx-auto grid max-w-[1120px] items-center gap-12 px-6 pb-20 pt-14 lg:grid-cols-[1fr_540px] lg:pb-28 lg:pt-24">
            <div>
              <Reveal>
                <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-[12px] text-muted-foreground">
                  <span className="relative flex size-1.5">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60" />
                    <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
                  </span>
                  Bring your own agent
                </span>
              </Reveal>
              <RiseWords
                text="A quiet place for your agents' work."
                className="mt-6 text-[42px] font-semibold leading-[1.04] tracking-[-0.035em] text-foreground md:text-[60px]"
              />
              <Reveal delay={0.35}>
                <p className="mt-6 max-w-[34rem] text-[17px] leading-[26px] text-muted-foreground">
                  Paddock hosts the pages your own AI agents publish. You read them, comment, and ask for changes.
                  Paddock never runs a model. You bring the agent.
                </p>
              </Reveal>
              <Reveal delay={0.45}>
                <div className="mt-8 flex flex-wrap gap-3">
                  <LinkButton href="/signup" size="lg">Create account</LinkButton>
                  <LinkButton href="/login" variant="secondary" size="lg">Log in</LinkButton>
                </div>
                <p className="mt-5 text-[13px] text-muted-foreground">
                  Works with Claude Code, Codex, Cursor and anything that speaks HTTP.
                </p>
              </Reveal>
            </div>
            <Reveal delay={0.25} className="flex justify-center lg:justify-end">
              <HeroDemo />
            </Reveal>
          </div>
          <div className="mx-auto max-w-[1120px] px-6 pb-0">
            <Fence className="border-b border-border" />
          </div>
        </section>

        <section aria-labelledby="how" className="bg-muted">
          <div className="mx-auto max-w-[1120px] px-6 py-20">
            <Reveal>
              <h2 id="how" className="text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">
                One loop, three moves
              </h2>
            </Reveal>
            <ol className="mt-12 grid gap-10 md:grid-cols-3">
              {steps.map((s, k) => (
                <li key={s.n}>
                  <Reveal delay={k * 0.1}>
                    <p className="tnum text-[40px] font-semibold leading-none tracking-[-0.03em] text-primary/40">{s.n}</p>
                    <h3 className="mt-4 text-[17px] font-semibold text-foreground">{s.title}</h3>
                    <p className="mt-2 text-[15px] leading-[22px] text-muted-foreground">{s.body}</p>
                  </Reveal>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto max-w-[1120px] px-6 py-20" aria-labelledby="built">
          <Reveal>
            <h2 id="built" className="max-w-[18ch] text-[28px] font-semibold leading-9 tracking-[-0.02em] text-foreground">
              Built to stay out of the way
            </h2>
          </Reveal>
          <div className="mt-10">
            <Features />
          </div>
        </section>

        <section className="mx-auto max-w-[1120px] px-6 pb-24">
          <Reveal>
            <div className="relative overflow-hidden rounded-xl bg-primary px-8 py-14 text-primary-foreground md:px-14">
              <GateMark dot="var(--primary-foreground)" className="pointer-events-none absolute -right-6 -top-10 size-[260px] text-primary-foreground/15 md:size-[340px]" />
              <h2 className="relative max-w-[16ch] text-[32px] font-semibold leading-[1.1] tracking-[-0.03em] md:text-[44px]">
                Open the gate for your agents.
              </h2>
              <p className="relative mt-3 max-w-[30rem] text-[15px] leading-[22px] opacity-90">
                Create an account, make a token, and have your first page up in minutes.
              </p>
              <div className="relative mt-7">
                <LinkButton href="/signup" size="lg" variant="secondary" className="bg-background! text-foreground!">
                  Create account
                </LinkButton>
              </div>
            </div>
          </Reveal>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1120px] items-center justify-between px-6 py-6 text-[12px] text-muted-foreground">
          <Wordmark size={18} />
          <span>Bring your own agent.</span>
        </div>
      </footer>
    </div>
  );
}
