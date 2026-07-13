"use client"

import { useEffect, useState } from "react"
import { useTheme } from "next-themes"
import { Sun, Moon, Monitor } from "lucide-react"
import { cn } from "@/lib/utils"

const OPTIONS = [
    { value: "light", label: "Clair", icon: Sun },
    { value: "dark", label: "Sombre", icon: Moon },
    { value: "system", label: "Système", icon: Monitor },
] as const

export function ThemeToggle() {
    const { theme, setTheme } = useTheme()
    // next-themes ne connaît le thème réel qu'après le montage (lecture de localStorage côté
    // client) — rendre les boutons non actifs avant ça évite un flash "mauvaise sélection".
    const [mounted, setMounted] = useState(false)
    // "mounted" can only become true after client-side hydration — there is no
    // initial value to compute it from, so this is a legitimate synchronous setState.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(() => setMounted(true), [])

    return (
        <div className="inline-flex items-center gap-1 rounded-full border bg-muted/30 p-1">
            {OPTIONS.map(({ value, label, icon: Icon }) => (
                <button
                    key={value}
                    type="button"
                    onClick={() => setTheme(value)}
                    aria-pressed={mounted && theme === value}
                    className={cn(
                        "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                        mounted && theme === value
                            ? "bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:text-foreground"
                    )}
                >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                </button>
            ))}
        </div>
    )
}
