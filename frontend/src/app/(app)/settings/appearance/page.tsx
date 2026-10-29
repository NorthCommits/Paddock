"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { Section } from "@/components/section";
import { useTheme } from "@/lib/theme";
import type { Theme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const options: { id: Theme; label: string; hint: string; icon: typeof Sun }[] = [
  { id: "system", label: "System", hint: "Match this device", icon: Monitor },
  { id: "light", label: "Light", hint: "Warm paper", icon: Sun },
  { id: "dark", label: "Dark", hint: "Easy on the eyes", icon: Moon },
];

export default function Page() {
  const [theme, setTheme] = useTheme();
  return (
    <Section title="Theme" hint="Saved to your account, so it follows you to every device. Signed out pages follow your device.">
      <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-3">
        {options.map(({ id, label, hint, icon: Icon }) => {
          const on = theme === id;
          return (
            <button
              key={id}
              role="radio"
              aria-checked={on}
              onClick={() => setTheme(id)}
              className={cn(
                "relative flex flex-col items-start gap-2 rounded-xl border bg-card p-4 text-left shadow-card transition-[border-color,box-shadow] duration-[120ms] hover:border-subtle",
                on ? "border-primary ring-[3px] ring-primary/20" : "border-border",
              )}
            >
              <Icon size={20} aria-hidden="true" className={on ? "text-primary" : "text-muted-foreground"} />
              <span>
                <span className="block text-[13px] font-medium text-foreground">{label}</span>
                <span className="block text-[12px] text-muted-foreground">{hint}</span>
              </span>
              {on && <Check size={16} aria-hidden="true" className="absolute right-3 top-3 text-primary" />}
            </button>
          );
        })}
      </div>
    </Section>
  );
}
