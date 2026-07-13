"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Image from "next/image"
import Link from "next/link"
import { ArrowLeft, Eye, EyeOff } from "lucide-react"
import { LanguageToggle } from "@/components/LanguageToggle"
import { useLocale } from "@/lib/i18n/LocaleContext"

export default function LoginPage() {
    return <LoginForm />
}

function LoginForm() {
    const router = useRouter()
    const { messages: t } = useLocale()
    const [error, setError] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [showPassword, setShowPassword] = useState(false)
    const [needsVerification, setNeedsVerification] = useState(false)
    const [pendingEmail, setPendingEmail] = useState("")
    const [isResending, setIsResending] = useState(false)
    const [resendSent, setResendSent] = useState(false)

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setError("")
        setNeedsVerification(false)
        setResendSent(false)
        setIsLoading(true)

        const formData = new FormData(event.currentTarget)
        const email = formData.get("email") as string
        const password = formData.get("password")

        try {
            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            })

            const data = await response.json()

            if (response.ok) {
                localStorage.setItem("username", data.username)
                localStorage.setItem("user_email", email)
                router.push("/dashboard")
                router.refresh()
            } else if (typeof data.detail === "object" && data.detail?.code === "email_not_verified") {
                setNeedsVerification(true)
                setPendingEmail(email)
                setError(data.detail.message || t.login.errorEmailNotVerified)
            } else if (typeof data.detail === "string") {
                setError(data.detail)
            } else if (Array.isArray(data.detail)) {
                setError(data.detail[0]?.msg || t.login.errorInvalidData)
            } else {
                setError(t.login.errorLoginFailed)
            }
        } catch {
            setError(t.login.errorNetwork)
        } finally {
            setIsLoading(false)
        }
    }

    async function handleResendVerification() {
        setIsResending(true)
        try {
            await fetch("/api/resend-verification", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: pendingEmail }),
            })
        } finally {
            setResendSent(true)
            setIsResending(false)
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
                    {t.login.backToHome}
                </Link>
                <div className="flex items-center gap-3">
                    <LanguageToggle />
                    <div className="flex items-center gap-2 font-bold text-slate-800">
                        <Image src="/logo_smartticket.png" alt="SmartTicket" width={28} height={28} className="h-7 w-7" />
                        <span>SmartTicket</span>
                    </div>
                </div>
            </header>

            {/* Form */}
            <div className="flex-1 flex items-center justify-center px-4 py-12">
                <div className="w-full max-w-md">

                    {/* Card */}
                    <div className="bg-white rounded-2xl shadow-xl shadow-indigo-100/50 border border-slate-100 p-8">

                        {/* Logo + Title */}
                        <div className="text-center mb-8">
                            <div className="inline-flex items-center justify-center w-12 h-12 mb-4">
                                <Image src="/logo_smartticket.png" alt="SmartTicket" width={48} height={48} className="w-12 h-12" />
                            </div>
                            <h1 className="text-2xl font-bold text-slate-900">{t.login.title}</h1>
                            <p className="text-slate-500 text-sm mt-1">
                                {t.login.subtitle}
                            </p>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-5">

                            {error && (
                                <div className="p-3 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl space-y-2">
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                                        {error}
                                    </div>
                                    {needsVerification && (
                                        resendSent ? (
                                            <p className="text-xs text-red-600">{t.login.verificationResent}</p>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={handleResendVerification}
                                                disabled={isResending}
                                                className="text-xs font-medium text-indigo-600 hover:text-indigo-700 hover:underline disabled:opacity-60"
                                            >
                                                {isResending ? t.login.resending : t.login.resendVerification}
                                            </button>
                                        )
                                    )}
                                </div>
                            )}

                            {/* Email */}
                            <div className="space-y-1.5">
                                <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                                    {t.login.emailLabel}
                                </label>
                                <input
                                    id="email"
                                    name="email"
                                    type="email"
                                    placeholder={t.login.emailPlaceholder}
                                    required
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                />
                            </div>

                            {/* Password */}
                            <div className="space-y-1.5">
                                <div className="flex items-center justify-between">
                                    <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                                        {t.login.passwordLabel}
                                    </label>
                                    <Link
                                        href="/forgot-password"
                                        className="text-xs text-indigo-600 hover:text-indigo-700 hover:underline"
                                    >
                                        {t.login.forgotPassword}
                                    </Link>
                                </div>
                                <div className="relative">
                                    <input
                                        id="password"
                                        name="password"
                                        type={showPassword ? "text" : "password"}
                                        required
                                        className="w-full px-4 py-2.5 pr-11 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                                    >
                                        {showPassword
                                            ? <EyeOff className="h-4 w-4" />
                                            : <Eye className="h-4 w-4" />
                                        }
                                    </button>
                                </div>
                            </div>

                            {/* Submit */}
                            <button
                                type="submit"
                                disabled={isLoading}
                                className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:ring-offset-2"
                            >
                                {isLoading ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        {t.login.submitting}
                                    </span>
                                ) : t.login.submit}
                            </button>
                        </form>

                        {/* Divider */}
                        <div className="flex items-center gap-3 my-6">
                            <div className="flex-1 h-px bg-slate-100" />
                            <span className="text-xs text-slate-400">{t.login.or}</span>
                            <div className="flex-1 h-px bg-slate-100" />
                        </div>

                        {/* Sign up */}
                        <p className="text-center text-sm text-slate-500">
                            {t.login.noAccount}{" "}
                            <Link href="/sign-up" className="text-indigo-600 font-medium hover:text-indigo-700 hover:underline">
                                {t.login.createAccount}
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
}
