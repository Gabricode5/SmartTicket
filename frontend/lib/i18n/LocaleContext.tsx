"use client"

import { createContext, useContext, useEffect, useState } from "react"
import { translations, type Locale, type Messages } from "./translations"

type LocaleContextValue = {
    locale: Locale
    setLocale: (locale: Locale) => void
    messages: Messages
}

const LocaleContext = createContext<LocaleContextValue | null>(null)

const STORAGE_KEY = "locale"

export function LocaleProvider({ children }: { children: React.ReactNode }) {
    const [locale, setLocaleState] = useState<Locale>("fr")

    // Pas de lecture de cookie côté serveur (garde le rendu statique) — la préférence
    // n'est donc appliquée qu'après le montage, avec un bref retour au français par défaut.
    useEffect(() => {
        const stored = window.localStorage.getItem(STORAGE_KEY)
        // localStorage is only readable client-side after mount — there is no
        // initial value to compute it from, so this is a legitimate synchronous setState.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (stored === "fr" || stored === "en") setLocaleState(stored)
    }, [])

    const setLocale = (next: Locale) => {
        setLocaleState(next)
        window.localStorage.setItem(STORAGE_KEY, next)
    }

    return (
        <LocaleContext.Provider value={{ locale, setLocale, messages: translations[locale] }}>
            {children}
        </LocaleContext.Provider>
    )
}

export function useLocale() {
    const ctx = useContext(LocaleContext)
    if (!ctx) throw new Error("useLocale must be used within a LocaleProvider")
    return ctx
}
