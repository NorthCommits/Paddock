import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Field({
  label,
  error,
  hint,
  id,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string; id: string }) {
  return (
    <div className="flex flex-col gap-1.5" data-invalid={error ? "true" : undefined}>
      <label htmlFor={id} className="text-[12px] font-medium text-muted-foreground">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined}
        {...props}
        className={cn(
          "h-10 w-full rounded-md border border-border bg-card px-3 text-[15px] text-foreground placeholder:text-subtle transition-[border-color,box-shadow] duration-[120ms] hover:border-subtle focus-visible:border-primary focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/25 aria-[invalid=true]:border-destructive",
          className,
        )}
      />
      {error ? (
        <p id={`${id}-err`} role="alert" className="text-[12px] text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-[12px] text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
