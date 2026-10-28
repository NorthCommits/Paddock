"use client";

import { Check, Circle, Eye, EyeOff } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { passwordChecks, passwordStrength } from "@/lib/password";
import { cn } from "@/lib/utils";

const colors = ["bg-border", "bg-destructive", "bg-warning", "bg-primary/70", "bg-primary"];

export function PasswordField({
  id,
  name,
  label = "Password",
  meter = false,
  autoComplete,
  error,
  extras = [],
}: {
  id: string;
  name: string;
  label?: string;
  meter?: boolean;
  autoComplete?: string;
  error?: string;
  extras?: string[];
}) {
  const [show, setShow] = useState(false);
  const [value, setValue] = useState("");
  const s = passwordStrength(value, extras);
  const checks = passwordChecks(value, extras);
  const describedBy = [error ? `${id}-err` : null, meter ? `${id}-meter` : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[12px] font-medium text-muted-foreground">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          name={name}
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoComplete={autoComplete}
          autoCapitalize="none"
          spellCheck={false}
          aria-invalid={!!error}
          aria-describedby={describedBy}
          required
          className="h-10 w-full rounded-md border border-input-border bg-card pl-3 pr-11 text-[15px] text-foreground transition-[border-color,box-shadow] duration-[120ms] hover:border-subtle focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25 aria-[invalid=true]:border-destructive"
        />
        <button
          type="button"
          onClick={() => setShow((v) => !v)}
          aria-label={show ? "Hide password" : "Show password"}
          aria-pressed={show}
          className="absolute right-1 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground"
        >
          {show ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>

      {meter && (
        <div id={`${id}-meter`} className="space-y-1.5">
          <div className="flex gap-1" aria-hidden="true">
            {[1, 2, 3, 4].map((i) => (
              <motion.span
                key={i}
                className={cn("h-1 flex-1 rounded-full transition-colors duration-300", s.level >= i ? colors[s.level] : "bg-border")}
                initial={false}
                animate={{ scaleY: s.level >= i ? 1 : 0.6 }}
                transition={{ duration: 0.2 }}
              />
            ))}
          </div>
          <ul className="space-y-1 pt-1">
            {checks.map((c) => (
              <li key={c.id} className={cn("flex items-center gap-2 text-[12px] transition-colors duration-200", c.ok ? "text-foreground" : "text-muted-foreground")}>
                <span className={cn("flex size-4 items-center justify-center rounded-full transition-colors duration-200", c.ok ? "bg-primary text-primary-foreground" : "text-subtle")}>
                  {c.ok ? <Check size={10} strokeWidth={3} aria-hidden="true" /> : <Circle size={10} aria-hidden="true" />}
                </span>
                {c.label}
                <span className="sr-only">{c.ok ? ", done" : ", not yet"}</span>
              </li>
            ))}
          </ul>
          <p className="flex justify-between gap-3 text-[12px]" aria-live="polite">
            <span className="text-muted-foreground">{s.tip}</span>
            {s.label && (
              <span className={cn("shrink-0 font-medium", s.level <= 1 ? "text-destructive" : s.level === 2 ? "text-warning" : "text-primary")}>
                {s.label}
              </span>
            )}
          </p>
        </div>
      )}

      {error && (
        <p id={`${id}-err`} role="alert" className="text-[12px] text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
