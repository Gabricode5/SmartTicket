"use client"

import { useState } from "react"
import Link from "next/link"
import { ArrowLeft, MailCheck } from "lucide-react"

export default function ForgotPasswordPage() {
    const [error, setError] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [sent, setSent] = useState(false)

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setError("")
        setIsLoading(true)

        const formData = new FormData(event.currentTarget)
        const email = formData.get("email")

        try {
            const response = await fetch("/api/forgot-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email }),
            })
            if (response.ok) {
                setSent(true)
            } else {
                setError("Impossible d'envoyer le lien pour le moment. Réessayez plus tard.")
            }
        } catch {
            setError("Impossible de contacter le serveur.")
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/40 to-white flex flex-col">
            <header className="p-6 flex items-center justify-between">
                <Link
                    href="/"
                    className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition-colors group"
                >
                    <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
                    Retour à l&apos;accueil
                </Link>
                <div className="flex items-center gap-2 font-bold text-slate-800">
                    <div className="h-7 w-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-xs font-bold">S</div>
                    <span>SmartTicket</span>
                </div>
            </header>

            <div className="flex-1 flex items-center justify-center px-4 py-12">
                <div className="w-full max-w-md">
                    <div className="bg-white rounded-2xl shadow-xl shadow-indigo-100/50 border border-slate-100 p-8">
                        {sent ? (
                            <div className="text-center">
                                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-100 mb-4">
                                    <MailCheck className="h-6 w-6 text-emerald-600" />
                                </div>
                                <h1 className="text-2xl font-bold text-slate-900">Vérifiez votre boîte mail</h1>
                                <p className="text-slate-500 text-sm mt-2">
                                    Si un compte existe avec cette adresse, un lien de réinitialisation vient d&apos;être envoyé. Le lien expire dans 1 heure.
                                </p>
                                <Link
                                    href="/login"
                                    className="mt-6 inline-block w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl transition-colors"
                                >
                                    Retour à la connexion
                                </Link>
                            </div>
                        ) : (
                            <>
                                <div className="text-center mb-7">
                                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-600 mb-4">
                                        <span className="text-white text-xl font-bold">S</span>
                                    </div>
                                    <h1 className="text-2xl font-bold text-slate-900">Mot de passe oublié ?</h1>
                                    <p className="text-slate-500 text-sm mt-1">Entrez votre email pour recevoir un lien de réinitialisation</p>
                                </div>

                                <form onSubmit={handleSubmit} className="space-y-4">
                                    {error && (
                                        <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl">
                                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                                            {error}
                                        </div>
                                    )}

                                    <div className="space-y-1.5">
                                        <label htmlFor="email" className="block text-sm font-medium text-slate-700">Adresse email</label>
                                        <input
                                            id="email" name="email" type="email" placeholder="vous@exemple.com" required
                                            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                        />
                                    </div>

                                    <button
                                        type="submit"
                                        disabled={isLoading}
                                        className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-xl transition-colors"
                                    >
                                        {isLoading ? "Envoi…" : "Envoyer le lien"}
                                    </button>
                                </form>

                                <p className="text-center text-sm text-slate-500 mt-6">
                                    <Link href="/login" className="text-indigo-600 font-medium hover:text-indigo-700 hover:underline inline-flex items-center gap-1">
                                        <ArrowLeft className="h-3.5 w-3.5" />
                                        Retour à la connexion
                                    </Link>
                                </p>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
