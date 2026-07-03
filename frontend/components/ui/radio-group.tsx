"use client"

import * as React from "react"
import { Circle } from "lucide-react"

import { cn } from "@/lib/utils"

type RadioGroupContextValue = {
    value?: string
    onValueChange?: (value: string) => void
    name?: string
    disabled?: boolean
}

const RadioGroupContext = React.createContext<RadioGroupContextValue | null>(null)

type RadioGroupProps = Omit<React.HTMLAttributes<HTMLDivElement>, "onChange"> & {
    defaultValue?: string
    value?: string
    onValueChange?: (value: string) => void
    name?: string
    disabled?: boolean
}

const RadioGroup = React.forwardRef<HTMLDivElement, RadioGroupProps>(
    ({ className, defaultValue, value: valueProp, onValueChange, name, disabled, ...props }, ref) => {
        const [internalValue, setInternalValue] = React.useState(defaultValue)
        const value = valueProp ?? internalValue

        const handleValueChange = React.useCallback((nextValue: string) => {
            if (valueProp === undefined) {
                setInternalValue(nextValue)
            }
            onValueChange?.(nextValue)
        }, [onValueChange, valueProp])

        return (
            <RadioGroupContext.Provider
                value={{
                    value,
                    onValueChange: handleValueChange,
                    name,
                    disabled,
                }}
            >
                <div
                    ref={ref}
                    role="radiogroup"
                    className={cn("grid gap-2", className)}
                    {...props}
                />
            </RadioGroupContext.Provider>
        )
    }
)
RadioGroup.displayName = "RadioGroup"

type RadioGroupItemProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "value" | "onChange"> & {
    value: string
}

const RadioGroupItem = React.forwardRef<HTMLButtonElement, RadioGroupItemProps>(
    ({ className, value, disabled, ...props }, ref) => {
        const context = React.useContext(RadioGroupContext)

        if (!context) {
            throw new Error("RadioGroupItem must be used within RadioGroup")
        }

        const checked = context.value === value
        const isDisabled = context.disabled || disabled

        return (
            <button
                ref={ref}
                type="button"
                role="radio"
                aria-checked={checked}
                data-state={checked ? "checked" : "unchecked"}
                data-disabled={isDisabled ? "" : undefined}
                disabled={isDisabled}
                onClick={() => context.onValueChange?.(value)}
                className={cn(
                    "inline-flex aspect-square h-4 w-4 items-center justify-center rounded-full border border-primary text-primary shadow-sm transition focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
                    checked ? "bg-primary/10" : "bg-background",
                    className
                )}
                {...props}
            >
                <span className="sr-only">{value}</span>
                {checked ? <Circle className="h-2.5 w-2.5 fill-primary text-primary" /> : null}
            </button>
        )
    }
)
RadioGroupItem.displayName = "RadioGroupItem"

export { RadioGroup, RadioGroupItem }
