"use client"

import { Suspense, useState } from "react"
import { useSearchParams } from "next/navigation"
import Image from "next/image"
import Link from "next/link"
import { ArrowLeft, CheckCircle2, Eye, EyeOff, XCircle } from "lucide-react"

type TokenErrorCode = "invalid_token" | "token_already_used" | "token_expired"

const TOKEN_ERROR_MESSAGES: Record<TokenErrorCode, string> = {
    invalid_token: "Ce lien de configuration est invalide. Vérifiez que vous avez copié l'adresse complète, ou contactez votre fournisseur SmartTicket pour en recevoir un nouveau.",
    token_already_used: "Ce lien a déjà été utilisé pour configurer le compte. Si ce n'est pas vous, contactez immédiatement votre fournisseur SmartTicket.",
    token_expired: "Ce lien a expiré. Contactez votre fournisseur SmartTicket pour en recevoir un nouveau.",
}

function SetupContent() {
    const searchParams = useSearchParams()
    const token = searchParams.get("token")

    const [username, setUsername] = useState("")
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [confirmPassword, setConfirmPassword] = useState("")
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState("")
    const [tokenErrorCode, setTokenErrorCode] = useState<TokenErrorCode | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [success, setSuccess] = useState(false)

    const passwordsMatch = confirmPassword === "" || password === confirmPassword

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setError("")
        setTokenErrorCode(null)

        if (!token) { setTokenErrorCode("invalid_token"); return }
        if (!username.trim()) { setError("Le nom d'utilisateur ne peut pas être vide."); return }
        if (password.length < 12) { setError("Le mot de passe doit contenir au moins 12 caractères (compte administrateur)."); return }
        if (password !== confirmPassword) { setError("Les mots de passe ne correspondent pas."); return }

        setIsLoading(true)
        try {
            const response = await fetch("/api/setup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token, username: username.trim(), email, password }),
            })
            if (response.ok) {
                setSuccess(true)
                return
            }
            const data = await response.json().catch(() => ({}))
            if (data.detail && typeof data.detail === "object" && data.detail.code in TOKEN_ERROR_MESSAGES) {
                setTokenErrorCode(data.detail.code as TokenErrorCode)
            } else {
                setError(typeof data.detail === "string" ? data.detail : "Une erreur est survenue.")
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
                    <Image src="/logo_smartticket.png" alt="SmartTicket" width={28} height={28} className="h-7 w-7" />
                    <span>SmartTicket</span>
                </div>
            </header>

            <div className="flex-1 flex items-center justify-center px-4 py-12">
                <div className="w-full max-w-md">
                    <div className="bg-white rounded-2xl shadow-xl shadow-indigo-100/50 border border-slate-100 p-8">
                        {success ? (
                            <div className="text-center">
                                <CheckCircle2 className="h-12 w-12 text-emerald-600 mx-auto mb-4" />
                                <h1 className="text-xl font-bold text-slate-900">Configuration terminée !</h1>
                                <p className="text-slate-500 text-sm mt-2 mb-6">
                                    Votre compte administrateur est prêt. Vous pouvez maintenant vous connecter.
                                </p>
                                <Link
                                    href="/login"
                                    className="inline-block w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl transition-colors"
                                >
                                    Se connecter
                                </Link>
                            </div>
                        ) : tokenErrorCode ? (
                            <div className="text-center">
                                <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                                <h1 className="text-xl font-bold text-slate-900">Lien indisponible</h1>
                                <p className="text-slate-500 text-sm mt-2">
                                    {TOKEN_ERROR_MESSAGES[tokenErrorCode]}
                                </p>
                            </div>
                        ) : (
                            <>
                                <div className="text-center mb-7">
                                    <div className="inline-flex items-center justify-center w-12 h-12 mb-4">
                                        <Image src="/logo_smartticket.png" alt="SmartTicket" width={48} height={48} className="w-12 h-12" />
                                    </div>
                                    <h1 className="text-2xl font-bold text-slate-900">Configurer votre compte</h1>
                                    <p className="text-slate-500 text-sm mt-1">Choisissez vos identifiants administrateur SmartTicket</p>
                                </div>

                                <form onSubmit={handleSubmit} className="space-y-4">
                                    {error && (
                                        <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl">
                                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                                            {error}
                                        </div>
                                    )}

                                    <div className="space-y-1.5">
                                        <label htmlFor="username" className="block text-sm font-medium text-slate-700">Nom d&apos;utilisateur</label>
                                        <input
                                            id="username"
                                            type="text"
                                            value={username}
                                            onChange={(e) => setUsername(e.target.value)}
                                            required
                                            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                        />
                                    </div>

                                    <div className="space-y-1.5">
                                        <label htmlFor="email" className="block text-sm font-medium text-slate-700">Adresse email</label>
                                        <input
                                            id="email"
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            required
                                            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                        />
                                    </div>

                                    <div className="space-y-1.5">
                                        <label htmlFor="password" className="block text-sm font-medium text-slate-700">Mot de passe</label>
                                        <p className="text-xs text-slate-400">Au moins 12 caractères — ce compte administre votre instance SmartTicket.</p>
                                        <div className="relative">
                                            <input
                                                id="password"
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
                                    </div>

                                    <div className="space-y-1.5">
                                        <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700">Confirmer le mot de passe</label>
                                        <input
                                            id="confirmPassword"
                                            type={showPassword ? "text" : "password"}
                                            value={confirmPassword}
                                            onChange={(e) => setConfirmPassword(e.target.value)}
                                            required
                                            className={`w-full px-4 py-2.5 rounded-xl border bg-slate-50 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:bg-white transition-all ${
                                                !passwordsMatch
                                                    ? "border-red-300 focus:ring-red-500/30 focus:border-red-400"
                                                    : "border-slate-200 focus:ring-indigo-500/30 focus:border-indigo-400"
                                            }`}
                                        />
                                        {!passwordsMatch && (
                                            <p className="text-xs text-red-500">Les mots de passe ne correspondent pas.</p>
                                        )}
                                    </div>

                                    <button
                                        type="submit"
                                        disabled={isLoading}
                                        className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-xl transition-colors"
                                    >
                                        {isLoading ? "Configuration…" : "Configurer mon compte"}
                                    </button>
                                </form>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default function SetupPage() {
    return (
        <Suspense fallback={null}>
            <SetupContent />
        </Suspense>
    )
}
