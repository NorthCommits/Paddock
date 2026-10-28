"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Six boxes for a one-time code. Under the boxes there is one real input, so paste,
 * autofill from email, the number keypad and screen readers all work as they do for any field.
 */
export function OtpInput({
  id,
  name,
  label = "Code",
  length = 6,
  onChange,
}: {
  id: string;
  name?: string;
  label?: string;
  length?: number;
  onChange?: (v: string) => void;
}) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const active = Math.min(value.length, length - 1);

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[12px] font-medium text-muted-foreground">
        {label}
      </label>
      <div className="relative">
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${length}, minmax(0, 1fr))` }} aria-hidden="true">
          {Array.from({ length }).map((_, i) => (
            <div
              key={i}
              className={cn(
                "flex h-14 items-center justify-center rounded-md border bg-card font-mono text-[24px] font-semibold text-foreground transition-[border-color,box-shadow,transform] duration-150",
                focused && i === active ? "border-primary ring-[3px] ring-primary/25" : "border-input-border",
                value[i] && "scale-[1.03]",
              )}
            >
              {value[i] ?? (focused && i === active ? <span className="h-6 w-[2px] animate-[blink_1s_steps(2)_infinite] bg-primary" /> : "")}
            </div>
          ))}
        </div>
        <input
          id={id}
          name={name}
          value={value}
          onChange={(e) => {
            const v = e.target.value.replace(/\D/g, "").slice(0, length);
            setValue(v);
            onChange?.(v);
          }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={length}
          pattern="\d*"
          className="absolute inset-0 size-full cursor-text opacity-0"
        />
      </div>
    </div>
  );
}
