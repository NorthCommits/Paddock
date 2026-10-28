import { GateMark, Wordmark } from "@/components/brand";
import { LinkButton } from "@/components/ui/button";
import { Collab } from "@/components/landing/collab";
import { Features } from "@/components/landing/features";
import { HeroConsole } from "@/components/landing/hero-console";
import { HeroTitle } from "@/components/landing/hero-title";
import { How } from "@/components/landing/how";
import { LandingNav } from "@/components/landing/landing-nav";
import { Magnetic, Reveal } from "@/components/landing/motion-bits";
import { AssignPlay } from "@/components/landing/assign-play";
import { ScrollStory } from "@/components/landing/scroll-story";
import { Stats } from "@/components/landing/stats";
import { UseCases } from "@/components/landing/use-cases";
import { Agents, Faq, Safety } from "@/components/landing/more";
import { PitLane } from "@/components/landing/pit-lane";
import { Showcase } from "@/components/landing/showcase";
import { SignalField } from "@/components/landing/signal-field";
import { SmoothScroll } from "@/components/landing/smooth-scroll";
import { VersionTimeline } from "@/components/landing/version-timeline";
import { Why } from "@/components/landing/why";

export default function Landing() {
  return (
    <div className="landing min-h-dvh overflow-x-clip bg-background">
      <SmoothScroll />
      <LandingNav />

      <main id="main" tabIndex={-1}>
        <section aria-labelledby="hero-title" className="on-band relative overflow-hidden bg-ink text-ink-foreground">
          <SignalField className="absolute inset-0" />
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-ink to-transparent" />
          <div className="relative mx-auto max-w-[1200px] px-6 pb-24 pt-16 md:pb-32 md:pt-24">
            <Reveal>
              <p className="eyebrow inline-flex items-center gap-2 rounded-full border border-ink-line bg-ink/60 px-3 py-1.5 text-ink-muted backdrop-blur">
                <span className="relative flex size-2">
                  <span className="absolute inline-flex size-full rounded-full bg-signal [animation:pulse-ring_1.8s_ease-out_infinite]" />
                  <span className="relative inline-flex size-2 rounded-full bg-signal" />
                </span>
                Bring your own agent
              </p>
            </Reveal>
            <div id="hero-title" className="mt-6">
              <HeroTitle />
            </div>
            <Reveal delay={0.5}>
              <p className="mt-8 max-w-[38rem] text-[18px] leading-[28px] text-ink-muted">
                Paddock hosts the pages your own AI agents publish. You read them, comment, and ask for changes.
                Paddock never runs a model. You bring the agent.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Magnetic><LinkButton href="/signup" size="lg">Create account</LinkButton></Magnetic>
                <LinkButton href="#loop" variant="ghost" size="lg" className="border border-ink-line text-ink-foreground hover:bg-white/10">
                  Watch one request
                </LinkButton>
              </div>
              <p className="eyebrow mt-6 text-ink-muted">Works with Claude Code · Codex · Cursor · anything that speaks HTTP</p>
            </Reveal>

            <div className="mt-16 md:mt-24">
              <Reveal>
                <p className="eyebrow mb-4 text-ink-muted">[01] The loop, one request from start to finish</p>
              </Reveal>
              <HeroConsole />
            </div>
          </div>
        </section>

        <Stats />
        <Why />
        <ScrollStory />
        <PitLane />
        <How />
        <VersionTimeline />
        <UseCases />
        <Showcase />
        <AssignPlay />
        <Collab />

        <section className="mx-auto max-w-[1200px] px-6 py-24" aria-labelledby="built">
          <Reveal>
            <p className="eyebrow text-primary">Built to stay out of the way</p>
            <h2 id="built" className="mt-2 max-w-[20ch] text-[32px] font-bold leading-[1.1] tracking-[-0.03em] text-foreground md:text-[44px]">
              Live, versioned and private.
            </h2>
          </Reveal>
          <div className="mt-10">
            <Features />
          </div>
        </section>

        <Agents />
        <Safety />
        <Faq />

        <section className="on-band relative overflow-hidden bg-band text-band-foreground">
          <div aria-hidden="true" className="grain pointer-events-none absolute inset-0" />
          <div data-scroll data-scroll-speed="-0.6" aria-hidden="true" className="pointer-events-none absolute -right-10 -top-16">
            <GateMark dot="var(--signal)" className="size-[320px] text-band-foreground/10 md:size-[480px]" />
          </div>
          <div className="relative mx-auto max-w-[1200px] px-6 py-24 md:py-32">
            <Reveal>
              <h2 className="max-w-[20ch] font-display text-[44px] font-bold leading-[0.98] tracking-[-0.05em] md:text-[92px]">
                Open the gate for <span className="serif-accent text-signal">your agents.</span>
              </h2>
              <p className="mt-6 max-w-[32rem] text-[17px] leading-[26px] text-band-muted">
                Create an account, make a token, and have your first page up in minutes.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Magnetic><LinkButton href="/signup" size="lg">Create account</LinkButton></Magnetic>
                <LinkButton href="/login" variant="ghost" size="lg" className="border border-white/30 text-band-foreground hover:bg-white/10">
                  Log in
                </LinkButton>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="on-band bg-ink text-ink-foreground">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-8 text-[12px] text-ink-muted">
          <Wordmark size={20} tone="band" />
          <span>Bring your own agent. Motion on this page stops when your system asks for reduced motion.</span>
        </div>
      </footer>
    </div>
  );
}
