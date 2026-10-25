import { cva, type VariantProps } from "class-variance-authority";
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-[background-color,transform,box-shadow] duration-[120ms] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary-hover shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]",
        secondary: "bg-card text-foreground border border-border hover:bg-muted",
        ghost: "text-foreground hover:bg-muted",
        link: "text-primary hover:underline px-0",
        destructive: "bg-destructive text-white hover:opacity-90",
      },
      size: {
        sm: "h-7 px-2.5 text-[13px]",
        md: "h-8 px-3.5 text-[13px]",
        lg: "h-10 px-5 text-[15px]",
      },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

type Props = VariantProps<typeof buttonVariants>;

export function Button({
  variant,
  size,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & Props) {
  return <button data-slot="button" className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export function LinkButton({
  href,
  variant,
  size,
  className,
  children,
}: Props & { href: string; className?: string; children: ReactNode }) {
  return (
    <Link href={href} data-slot="button" className={cn(buttonVariants({ variant, size }), className)}>
      {children}
    </Link>
  );
}
