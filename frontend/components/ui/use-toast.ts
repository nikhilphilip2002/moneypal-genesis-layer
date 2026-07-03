// Minimal implementation of use-toast for immediate needs
import { useState, useEffect } from "react"

const TOAST_LIMIT = 1
const TOAST_REMOVE_DELAY = 1000000

type ToastType = {
    id: string
    title?: string
    description?: string
    action?: React.ReactNode
    variant?: "default" | "destructive"
}

let count = 0

function genId() {
    count = (count + 1) % Number.MAX_VALUE
    return count.toString()
}

type ToastInput = Omit<ToastType, "id">

const listeners: Array<(state: ToastType[]) => void> = []

let memoryState: ToastType[] = []

function dispatch(action: { type: "ADD_TOAST"; toast: ToastInput } | { type: "DISMISS_TOAST"; toastId?: string }) {
    switch (action.type) {
        case "ADD_TOAST":
            memoryState = [{ ...action.toast, id: genId() }, ...memoryState].slice(0, TOAST_LIMIT)
            break
        case "DISMISS_TOAST":
            // simplified
            memoryState = []
            break
    }
    listeners.forEach((listener) => listener(memoryState))
}

export function useToast() {
    const [state, setState] = useState<ToastType[]>(memoryState)

    useEffect(() => {
        listeners.push(setState)
        return () => {
            const index = listeners.indexOf(setState)
            if (index > -1) {
                listeners.splice(index, 1)
            }
        }
    }, [state])

    return {
        toast: (props: ToastInput) => {
            // Just log for now if we don't have a Toaster component
            console.log("Toast:", props)
            dispatch({ type: "ADD_TOAST", toast: props })
            return {
                id: genId(),
                dismiss: () => dispatch({ type: "DISMISS_TOAST" }),
                update: () => { },
            }
        },
        dismiss: (toastId?: string) => dispatch({ type: "DISMISS_TOAST", toastId }),
        toasts: state,
    }
}
