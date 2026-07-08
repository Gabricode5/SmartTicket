"use client"

import { useState } from "react"
import Link from "next/link"
import { ArrowLeft, Eye, EyeOff, MailCheck } from "lucide-react"

type Strength = { score: number; label: string; color: string; textColor: string }

function getStrength(password: string): Strength {
    if (!password) return { score: 0, label: "", color: "", textColor: "" }
    let score = 0
    if (password.length >= 6) score++
    if (password.length >= 10) score++
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++
    if (/[0-9]/.test(password)) score++
    if (/[^A-Za-z0-9]/.test(password)) score++

    if (score <= 1) return { score: 1, label: "Très faible", color: "bg-red-500", textColor: "text-red-500" }
    if (score === 2) return { score: 2, label: "Faible", color: "bg-orange-500", textColor: "text-orange-500" }
    if (score === 3) return { score: 3, label: "Moyen", color: "bg-yellow-500", textColor: "text-yellow-600" }
    if (score === 4) return { score: 4, label: "Fort", color: "bg-green-500", textColor: "text-green-600" }
    return { score: 5, label: "Très fort", color: "bg-emerald-600", textColor: "text-emerald-600" }
}

export default function SignUpPage() {
    const [error, setError] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [rgpdAccepted, setRgpdAccepted] = useState(false)
    const [password, setPassword] = useState("")
    const [confirmPassword, setConfirmPassword] = useState("")
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirm, setShowConfirm] = useState(false)
    const [registeredEmail, setRegisteredEmail] = useState("")

    const strength = getStrength(password)
    const passwordsMatch = confirmPassword === "" || password === confirmPassword
    const canSubmit = rgpdAccepted && password.length >= 6 && password === confirmPassword

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setError("")

        if (!rgpdAccepted) { setError("Vous devez accepter la politique de confidentialité."); return }
        if (password.length < 6) { setError("Le mot de passe doit contenir au moins 6 caractères."); return }
        if (password !== confirmPassword) { setError("Les mots de passe ne correspondent pas."); return }

        setIsLoading(true)
        const formData = new FormData(event.currentTarget)
        const data = Object.fromEntries(formData)
        const payload = { username: data.username, email: data.email, password, prenom: data.prenom, nom: data.nom }

        try {
            const response = await fetch("/api/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })
            if (response.ok) {
                const created = await response.json()
                setRegisteredEmail(created.email ?? String(data.email))
            } else {
                const errorData = await response.json()
                setError(errorData.detail || "Une erreur est survenue")
            }
        } catch {
            setError("Impossible de contacter le serveur.")
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/40 to-white flex flex-col">

            {/* Header */}
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

            {/* Form */}
            <div className="flex-1 flex items-center justify-center px-4 py-8">
                <div className="w-full max-w-md">
                    <div className="bg-white rounded-2xl shadow-xl shadow-indigo-100/50 border border-slate-100 p-8">
                    {registeredEmail ? (
                        <div className="text-center">
                            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-100 mb-4">
                                <MailCheck className="h-6 w-6 text-emerald-600" />
                            </div>
                            <h1 className="text-2xl font-bold text-slate-900">Vérifiez votre boîte mail</h1>
                            <p className="text-slate-500 text-sm mt-2">
                                Un lien de confirmation a été envoyé à <strong>{registeredEmail}</strong>. Cliquez dessus pour activer votre compte avant de vous connecter.
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
                        {/* Title */}
                        <div className="text-center mb-7">
                            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-600 mb-4">
                                <span className="text-white text-xl font-bold">S</span>
                            </div>
                            <h1 className="text-2xl font-bold text-slate-900">Créer un compte</h1>
                            <p className="text-slate-500 text-sm mt-1">Rejoignez SmartTicket gratuitement</p>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-4">

                            {error && (
                                <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl">
                                    <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                                    {error}
                                </div>
                            )}

                            {/* Prénom + Nom */}
                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1.5">
                                    <label htmlFor="prenom" className="block text-sm font-medium text-slate-700">Prénom</label>
                                    <input
                                        id="prenom" name="prenom" placeholder="Jean" required
                                        className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <label htmlFor="nom" className="block text-sm font-medium text-slate-700">Nom</label>
                                    <input
                                        id="nom" name="nom" placeholder="Dupont" required
                                        className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                    />
                                </div>
                            </div>

                            {/* Username */}
                            <div className="space-y-1.5">
                                <label htmlFor="username" className="block text-sm font-medium text-slate-700">Nom d&apos;utilisateur</label>
                                <input
                                    id="username" name="username" placeholder="jean_dupont" required
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                />
                            </div>

                            {/* Email */}
                            <div className="space-y-1.5">
                                <label htmlFor="email" className="block text-sm font-medium text-slate-700">Adresse email</label>
                                <input
                                    id="email" name="email" type="email" placeholder="vous@exemple.com" required
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                />
                            </div>

                            {/* Mot de passe */}
                            <div className="space-y-1.5">
                                <label htmlFor="password" className="block text-sm font-medium text-slate-700">Mot de passe</label>
                                <div className="relative">
                                    <input
                                        id="password" name="password"
                                        type={showPassword ? "text" : "password"}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                        className="w-full px-4 py-2.5 pr-11 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                    />
                                    <button type="button" onClick={() => setShowPassword(v => !v)} tabIndex={-1}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors">
                                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </button>
                                </div>
                                {password && (
                                    <div className="space-y-1 pt-1">
                                        <div className="flex gap-1">
                                            {[1, 2, 3, 4, 5].map((i) => (
                                                <div key={i} className={`h-1 flex-1 rounded-full transition-colors duration-300 ${i <= strength.score ? strength.color : "bg-slate-100"}`} />
                                            ))}
                                        </div>
                                        <p className={`text-xs font-medium ${strength.textColor}`}>{strength.label}</p>
                                    </div>
                                )}
                            </div>

                            {/* Confirmation */}
                            <div className="space-y-1.5">
                                <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700">Confirmer le mot de passe</label>
                                <div className="relative">
                                    <input
                                        id="confirmPassword"
                                        type={showConfirm ? "text" : "password"}
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        required
                                        className={`w-full px-4 py-2.5 pr-11 rounded-xl border bg-slate-50 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:bg-white transition-all ${
                                            !passwordsMatch
                                                ? "border-red-300 focus:ring-red-500/30 focus:border-red-400"
                                                : "border-slate-200 focus:ring-indigo-500/30 focus:border-indigo-400"
                                        }`}
                                    />
                                    <button type="button" onClick={() => setShowConfirm(v => !v)} tabIndex={-1}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors">
                                        {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </button>
                                </div>
                                {!passwordsMatch && (
                                    <p className="text-xs text-red-500">Les mots de passe ne correspondent pas.</p>
                                )}
                            </div>

                            {/* RGPD */}
                            <div className="flex items-start gap-3 pt-1">
                                <input
                                    id="rgpd" type="checkbox"
                                    checked={rgpdAccepted}
                                    onChange={(e) => setRgpdAccepted(e.target.checked)}
                                    className="mt-0.5 h-4 w-4 cursor-pointer accent-indigo-600 rounded"
                                />
                                <label htmlFor="rgpd" className="text-xs text-slate-500 leading-relaxed cursor-pointer">
                                    J&apos;accepte que mes données personnelles soient traitées pour gérer mon compte, conformément au{" "}
                                    <a href="https://www.cnil.fr/fr/rgpd-de-quoi-parle-t-on" target="_blank" rel="noopener noreferrer"
                                        className="text-indigo-600 hover:underline">RGPD</a>.
                                    Elles ne seront pas transmises à des tiers.
                                </label>
                            </div>

                            {/* Submit */}
                            <button
                                type="submit"
                                disabled={!canSubmit || isLoading}
                                className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:ring-offset-2"
                            >
                                {isLoading ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        Création du compte…
                                    </span>
                                ) : "Créer mon compte"}
                            </button>
                        </form>

                        <div className="flex items-center gap-3 my-5">
                            <div className="flex-1 h-px bg-slate-100" />
                            <span className="text-xs text-slate-400">ou</span>
                            <div className="flex-1 h-px bg-slate-100" />
                        </div>

                        <p className="text-center text-sm text-slate-500">
                            Déjà un compte ?{" "}
                            <Link href="/login" className="text-indigo-600 font-medium hover:text-indigo-700 hover:underline">
                                Se connecter
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
