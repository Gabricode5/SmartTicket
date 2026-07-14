"use client"

import { Suspense, useState } from "react"
import { useSearchParams } from "next/navigation"
import Image from "next/image"
import Link from "next/link"
import { ArrowLeft, CheckCircle2, Eye, EyeOff, XCircle } from "lucide-react"
import { useLocale } from "@/lib/i18n/LocaleContext"

type TokenErrorCode = "invalid_token" | "token_already_used" | "token_expired"

function SetupContent() {
    const searchParams = useSearchParams()
    const token = searchParams.get("token")
    const { messages: t } = useLocale()

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
        if (!username.trim()) { setError(t.setup.usernameEmpty); return }
        if (password.length < 12) { setError(t.setup.passwordTooShort); return }
        if (password !== confirmPassword) { setError(t.setup.passwordsDontMatch); return }

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
            if (data.detail && typeof data.detail === "object" && data.detail.code in t.setup.tokenErrors) {
                setTokenErrorCode(data.detail.code as TokenErrorCode)
            } else {
                setError(typeof data.detail === "string" ? data.detail : t.setup.genericError)
            }
        } catch {
            setError(t.setup.networkError)
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
                    {t.login.backToHome}
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
                                <h1 className="text-xl font-bold text-slate-900">{t.setup.successTitle}</h1>
                                <p className="text-slate-500 text-sm mt-2 mb-6">
                                    {t.setup.successBody}
                                </p>
                                <Link
                                    href="/login"
                                    className="inline-block w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl transition-colors"
                                >
                                    {t.setup.login}
                                </Link>
                            </div>
                        ) : tokenErrorCode ? (
                            <div className="text-center">
                                <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                                <h1 className="text-xl font-bold text-slate-900">{t.setup.unavailableLinkTitle}</h1>
                                <p className="text-slate-500 text-sm mt-2">
                                    {t.setup.tokenErrors[tokenErrorCode]}
                                </p>
                            </div>
                        ) : (
                            <>
                                <div className="text-center mb-7">
                                    <div className="inline-flex items-center justify-center w-12 h-12 mb-4">
                                        <Image src="/logo_smartticket.png" alt="SmartTicket" width={48} height={48} className="w-12 h-12" />
                                    </div>
                                    <h1 className="text-2xl font-bold text-slate-900">{t.setup.title}</h1>
                                    <p className="text-slate-500 text-sm mt-1">{t.setup.subtitle}</p>
                                </div>

                                <form onSubmit={handleSubmit} className="space-y-4">
                                    {error && (
                                        <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl">
                                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                                            {error}
                                        </div>
                                    )}

                                    <div className="space-y-1.5">
                                        <label htmlFor="username" className="block text-sm font-medium text-slate-700">{t.setup.usernameLabel}</label>
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
                                        <label htmlFor="email" className="block text-sm font-medium text-slate-700">{t.setup.emailLabel}</label>
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
                                        <label htmlFor="password" className="block text-sm font-medium text-slate-700">{t.setup.passwordLabel}</label>
                                        <p className="text-xs text-slate-400">{t.setup.passwordHint}</p>
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
                                        <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700">{t.setup.confirmPasswordLabel}</label>
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
                                            <p className="text-xs text-red-500">{t.setup.passwordsDontMatch}</p>
                                        )}
                                    </div>

                                    <button
                                        type="submit"
                                        disabled={isLoading}
                                        className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-xl transition-colors"
                                    >
                                        {isLoading ? t.setup.configuring : t.setup.configureAccount}
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
