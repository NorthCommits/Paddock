import type { ReactNode } from "react";

export function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-[15px] font-semibold text-foreground">{title}</h2>
      {hint && <p className="mt-0.5 text-[13px] text-muted-foreground">{hint}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}
