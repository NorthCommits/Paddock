import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div data-slot="skeleton" aria-hidden="true" className={cn("skeleton", className)} />;
}
