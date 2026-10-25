"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

const MARK =
  "M68 36H143A53 53 0 0 1 194.62 77H157.73A19 19 0 0 0 143 70H102V108H143A19 19 0 0 0 157.73 101H194.62A53 53 0 0 1 143 142H102V220H68Z";

export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 256 256" aria-hidden="true" className="text-accent">
      <rect width="256" height="256" rx="58" fill="currentColor" />
      <path transform="translate(20 4) scale(0.88)" fill="var(--on-accent)" d={MARK} />
    </svg>
  );
}

export function Wordmark({ size = 20 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Mark size={size} />
      <span className="font-semibold text-ink" style={{ fontSize: size * 0.85 }}>
        Paddock
      </span>
    </span>
  );
}

type Variant = "primary" | "secondary" | "plain" | "danger";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-on-accent hover:bg-accent-hover",
  secondary: "bg-grouped text-ink hover:bg-line",
  plain: "text-accent-ink hover:bg-grouped",
  danger: "bg-danger text-white hover:opacity-90",
};
const sizes: Record<Size, string> = {
  sm: "h-7 px-2.5 text-[13px]",
  md: "h-8 px-3.5 text-[13px]",
  lg: "h-10 px-5 text-[15px]",
};

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors duration-[120ms] disabled:opacity-50 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className}`}
    />
  );
}

export function LinkButton({
  href,
  variant = "secondary",
  size = "md",
  children,
}: {
  href: string;
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors duration-[120ms] ${variants[variant]} ${sizes[size]}`}
    >
      {children}
    </a>
  );
}

export function Field({
  label,
  error,
  hint,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string; id: string }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-[12px] font-medium text-ink-2">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined}
        {...props}
        className="h-10 w-full rounded-md border border-line bg-bg px-3 text-[15px] text-ink placeholder:text-ink-3 transition-colors duration-[120ms] hover:border-ink-3 aria-[invalid=true]:border-danger"
      />
      {error ? (
        <p id={`${id}-err`} role="alert" className="text-[12px] text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-[12px] text-ink-2">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "danger" | "accent" }) {
  const tones = {
    neutral: "bg-grouped text-ink-2",
    danger: "bg-grouped text-danger",
    accent: "bg-grouped text-accent-ink",
  };
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>{children}</span>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-start gap-3 py-16">
      <h2 className="text-[17px] font-semibold text-ink">{title}</h2>
      <p className="text-[15px] leading-[22px] text-ink-2">{body}</p>
      {action}
    </div>
  );
}

export function CopyField({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div className="flex items-start gap-2 rounded-md border border-line bg-grouped p-2.5">
      <pre className="min-w-0 flex-1 overflow-x-auto whitespace-pre font-mono text-[12px] leading-[18px] text-ink">
        {value}
      </pre>
      <Button size="sm" variant="secondary" onClick={copy} aria-label={`Copy ${label}`}>
        {copied ? <Check size={14} /> : <Copy size={14} />}
        <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
      </Button>
    </div>
  );
}

export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="anim-fade fixed inset-0 bg-black/30" />
        <Dialog.Content className="anim-sheet fixed left-1/2 top-[12vh] w-[calc(100%-32px)] max-w-md -translate-x-1/2 rounded-lg bg-surface p-5 shadow-float">
          <Dialog.Title className="text-[17px] font-semibold text-ink">{title}</Dialog.Title>
          <Dialog.Description className="mt-1 text-[13px] text-ink-2">{description}</Dialog.Description>
          <div className="mt-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
