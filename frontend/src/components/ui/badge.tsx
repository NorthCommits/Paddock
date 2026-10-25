import { cva, type VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium", {
  variants: {
    variant: {
      neutral: "bg-muted text-muted-foreground",
      success: "bg-primary-soft text-primary",
      destructive: "bg-muted text-destructive",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export function Badge({
  variant,
  className,
  children,
}: VariantProps<typeof badgeVariants> & { className?: string; children: ReactNode }) {
  return (
    <span data-slot="badge" className={cn(badgeVariants({ variant }), className)}>
      {children}
    </span>
  );
}
