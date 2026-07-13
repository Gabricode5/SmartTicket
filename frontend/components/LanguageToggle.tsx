"use client"

import { useLocale } from "@/lib/i18n/LocaleContext"
import { cn } from "@/lib/utils"
import type { Locale } from "@/lib/i18n/translations"

const OPTIONS: { value: Locale; label: string }[] = [
    { value: "fr", label: "Français" },
    { value: "en", label: "English" },
]

export function LanguageToggle({ className }: { className?: string }) {
    const { locale, setLocale } = useLocale()

    return (
        <div className={cn("inline-flex items-center gap-1 rounded-full border bg-muted/30 p-1", className)}>
            {OPTIONS.map(({ value, label }) => (
                <button
                    key={value}
                    type="button"
                    onClick={() => setLocale(value)}
                    aria-pressed={locale === value}
                    className={cn(
                        "px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                        locale === value
                            ? "bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:text-foreground"
                    )}
                >
                    {label}
                </button>
            ))}
        </div>
    )
}
