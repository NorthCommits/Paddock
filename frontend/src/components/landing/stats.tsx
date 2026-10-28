import { CountUp, Reveal } from "./motion-bits";

const stats = [
  { n: 0, label: "models run by Paddock", note: "You bring the agent" },
  { n: 1, label: "token per agent", note: "Revoke it at any time" },
  { n: 4, label: "stages for every request", note: "Open, claimed, publishing, done" },
];

/** Three facts about the product. The numbers count up once. */
export function Stats() {
  return (
    <section className="border-y border-border bg-background" aria-label="Paddock in numbers">
      <ul className="mx-auto grid max-w-[1200px] gap-px px-6 py-12 md:grid-cols-3 md:gap-8">
        {stats.map((s, i) => (
          <li key={s.label}><Reveal delay={i * 0.08}>
            <div className="py-4">
              <p className="font-display text-[64px] font-bold leading-none tracking-[-0.05em] text-primary">
                <CountUp to={s.n} />
              </p>
              <p className="mt-2 text-[16px] font-semibold text-foreground">{s.label}</p>
              <p className="text-[14px] text-muted-foreground">{s.note}</p>
            </div>
          </Reveal></li>
        ))}
      </ul>
    </section>
  );
}
