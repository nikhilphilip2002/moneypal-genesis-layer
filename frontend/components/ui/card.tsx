import * as React from "react"

import { cn } from "@/lib/utils"

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "relative rounded-2xl text-card-foreground",
      /* Apple-style glass: saturate is the key differentiator */
      "bg-white/62 dark:bg-[rgba(20,16,14,0.68)]",
      "backdrop-blur-[20px] [backdrop-filter:saturate(180%)_blur(20px)]",
      "[-webkit-backdrop-filter:saturate(180%)_blur(20px)]",
      /* Thin border with brighter top edge */
      "border border-white/75 dark:border-white/10",
      "[border-top-color:rgba(255,255,255,0.95)] dark:[border-top-color:rgba(255,255,255,0.22)]",
      /* Coloured shadow + inset highlight */
      "shadow-[0_8px_32px_rgba(221,122,58,0.12),0_2px_8px_rgba(221,122,58,0.06),0_1px_0_rgba(255,255,255,0.90)_inset]",
      "dark:shadow-[0_8px_40px_rgba(0,0,0,0.55),0_2px_8px_rgba(0,0,0,0.30),0_1px_0_rgba(255,255,255,0.08)_inset]",
      "transition-all duration-300",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("text-2xl font-semibold leading-none tracking-tight", className)}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
