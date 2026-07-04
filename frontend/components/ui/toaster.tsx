"use client"

import { useToast } from "@/components/ui/use-toast"
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"

export function Toaster() {
    const { toasts, dismiss } = useToast()

    if (toasts.length === 0) return null

    return (
        <div className="fixed bottom-0 right-0 z-[100] flex flex-col gap-2 p-4 max-w-[420px]">
            {toasts.map(function ({ id, title, description, variant }) {
                return (
                    <div
                        key={id}
                        className={`
                rounded-lg border p-4 shadow-lg transition-all
                ${variant === 'destructive'
                                ? 'bg-red-600 text-white border-red-600'
                                : 'bg-white text-gray-900 border-gray-200'}
            `}
                        onClick={() => dismiss(id)}
                    >
                        {title && <div className="font-semibold">{title}</div>}
                        {description && <div className="text-sm opacity-90">{description}</div>}
                    </div>
                )
            })}
        </div>
    )
}
