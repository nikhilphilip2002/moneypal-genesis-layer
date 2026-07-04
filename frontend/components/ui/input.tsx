import * as React from "react"

import { cn } from "@/lib/utils"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-xl px-3 py-2 text-sm",
          /* Apple vibrancy on inputs */
          "bg-white/55 dark:bg-white/6",
          "[backdrop-filter:saturate(180%)_blur(16px)]",
          "[-webkit-backdrop-filter:saturate(180%)_blur(16px)]",
          "border border-white/70 dark:border-white/14",
          "[border-top-color:rgba(255,255,255,0.92)] dark:[border-top-color:rgba(255,255,255,0.20)]",
          "shadow-[0_1px_4px_rgba(0,0,0,0.06),0_1px_0_rgba(255,255,255,0.80)_inset]",
          "dark:shadow-[0_1px_4px_rgba(0,0,0,0.30),0_1px_0_rgba(255,255,255,0.05)_inset]",
          "ring-offset-transparent",
          "file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
          "placeholder:text-muted-foreground/70",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-0",
          "focus-visible:border-ring/50 focus-visible:bg-white/70 dark:focus-visible:bg-white/10",
          "transition-all duration-200",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
