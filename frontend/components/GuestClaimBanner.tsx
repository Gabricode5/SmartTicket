"use client"

import { useState } from "react"
import { CheckCircle2 } from "lucide-react"

export function GuestClaimBanner() {
    const [open, setOpen] = useState(false)
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [success, setSuccess] = useState(false)

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setError("")
        setIsLoading(true)
        try {
            const response = await fetch("/api/me/claim", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            })
            if (response.ok) {
                setSuccess(true)
                setOpen(false)
            } else {
                const data = await response.json().catch(() => ({}))
                setError(typeof data.detail === "string" ? data.detail : "Erreur lors de la création du compte.")
            }
        } catch {
            setError("Impossible de contacter le serveur.")
        } finally {
            setIsLoading(false)
        }
    }

    if (success) {
        return (
            <div className="flex items-center gap-2 px-6 py-2.5 bg-emerald-50 border-b border-emerald-100 text-emerald-700 text-sm">
                <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                <span>Compte créé — vérifiez votre boîte mail pour confirmer votre adresse.</span>
            </div>
        )
    }

    return (
        <div className="border-b border-indigo-100 bg-indigo-50/60">
            <div className="flex items-center justify-between gap-3 px-6 py-2.5 text-sm text-indigo-700">
                <span>Conversation anonyme — créez un compte pour suivre votre ticket et être notifié des réponses.</span>
                <button
                    type="button"
                    onClick={() => setOpen((v) => !v)}
                    className="font-semibold underline underline-offset-2 shrink-0"
                >
                    {open ? "Fermer" : "Créer un compte"}
                </button>
            </div>
            {open && (
                <form onSubmit={handleSubmit} className="px-6 pb-3 flex flex-wrap items-end gap-2">
                    {error && <p className="w-full text-xs text-red-600">{error}</p>}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="guest-claim-email" className="text-[11px] text-indigo-600 font-medium">Email</label>
                        <input
                            id="guest-claim-email"
                            type="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="h-9 px-3 rounded-lg border border-indigo-200 bg-background text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                        />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label htmlFor="guest-claim-password" className="text-[11px] text-indigo-600 font-medium">Mot de passe</label>
                        <input
                            id="guest-claim-password"
                            type="password"
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="h-9 px-3 rounded-lg border border-indigo-200 bg-background text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={isLoading}
                        className="h-9 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-sm font-semibold"
                    >
                        {isLoading ? "Création…" : "Valider"}
                    </button>
                </form>
            )}
        </div>
    )
}
