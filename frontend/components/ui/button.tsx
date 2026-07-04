import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 active:scale-[0.97]",
  {
    variants: {
      variant: {
        /* Apple-style primary — glowing blue with ambient shadow */
        default:
          "bg-primary text-primary-foreground font-semibold " +
          "shadow-[0_4px_16px_rgba(0,93,170,0.30),0_1px_0_rgba(255,255,255,0.20)_inset] " +
          "hover:bg-primary/92 hover:shadow-[0_6px_20px_rgba(0,93,170,0.40),0_1px_0_rgba(255,255,255,0.20)_inset] " +
          "dark:shadow-[0_4px_16px_rgba(0,0,0,0.40),0_1px_0_rgba(255,255,255,0.10)_inset]",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        /* Glass outline — Apple vibrancy */
        outline:
          "border border-white/70 dark:border-white/12 " +
          "[border-top-color:rgba(255,255,255,0.92)] dark:[border-top-color:rgba(255,255,255,0.20)] " +
          "bg-white/45 dark:bg-white/6 " +
          "[backdrop-filter:saturate(180%)_blur(16px)] [-webkit-backdrop-filter:saturate(180%)_blur(16px)] " +
          "shadow-[0_2px_8px_rgba(0,0,0,0.06),0_1px_0_rgba(255,255,255,0.75)_inset] " +
          "dark:shadow-[0_2px_8px_rgba(0,0,0,0.30),0_1px_0_rgba(255,255,255,0.06)_inset] " +
          "hover:bg-white/65 dark:hover:bg-white/12 hover:border-white/90 " +
          "hover:shadow-[0_4px_16px_rgba(0,93,170,0.08),0_1px_0_rgba(255,255,255,0.80)_inset]",
        secondary:
          "bg-white/50 dark:bg-white/8 " +
          "[backdrop-filter:saturate(180%)_blur(12px)] [-webkit-backdrop-filter:saturate(180%)_blur(12px)] " +
          "border border-white/65 dark:border-white/12 " +
          "text-secondary-foreground shadow-sm " +
          "hover:bg-white/70 dark:hover:bg-white/14",
        ghost:
          "hover:bg-white/50 dark:hover:bg-white/8 " +
          "[backdrop-filter:saturate(160%)_blur(12px)] [-webkit-backdrop-filter:saturate(160%)_blur(12px)] " +
          "hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-11 rounded-xl px-8 text-[15px]",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
