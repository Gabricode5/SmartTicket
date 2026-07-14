"use client"

import { useState } from "react"
import Image from "next/image"
import Link from "next/link"
import { ArrowLeft, MailCheck } from "lucide-react"
import { useLocale } from "@/lib/i18n/LocaleContext"

export default function ForgotPasswordPage() {
    const { messages: t } = useLocale()
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
                setError(t.forgotPassword.sendError)
            }
        } catch {
            setError(t.forgotPassword.networkError)
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
                        {sent ? (
                            <div className="text-center">
                                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-100 mb-4">
                                    <MailCheck className="h-6 w-6 text-emerald-600" />
                                </div>
                                <h1 className="text-2xl font-bold text-slate-900">{t.forgotPassword.checkEmailTitle}</h1>
                                <p className="text-slate-500 text-sm mt-2">
                                    {t.forgotPassword.checkEmailBody}
                                </p>
                                <Link
                                    href="/login"
                                    className="mt-6 inline-block w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl transition-colors"
                                >
                                    {t.forgotPassword.backToLogin}
                                </Link>
                            </div>
                        ) : (
                            <>
                                <div className="text-center mb-7">
                                    <div className="inline-flex items-center justify-center w-12 h-12 mb-4">
                                        <Image src="/logo_smartticket.png" alt="SmartTicket" width={48} height={48} className="w-12 h-12" />
                                    </div>
                                    <h1 className="text-2xl font-bold text-slate-900">{t.forgotPassword.title}</h1>
                                    <p className="text-slate-500 text-sm mt-1">{t.forgotPassword.subtitle}</p>
                                </div>

                                <form onSubmit={handleSubmit} className="space-y-4">
                                    {error && (
                                        <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl">
                                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                                            {error}
                                        </div>
                                    )}

                                    <div className="space-y-1.5">
                                        <label htmlFor="email" className="block text-sm font-medium text-slate-700">{t.forgotPassword.emailLabel}</label>
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
                                        {isLoading ? t.forgotPassword.sending : t.forgotPassword.sendLink}
                                    </button>
                                </form>

                                <p className="text-center text-sm text-slate-500 mt-6">
                                    <Link href="/login" className="text-indigo-600 font-medium hover:text-indigo-700 hover:underline inline-flex items-center gap-1">
                                        <ArrowLeft className="h-3.5 w-3.5" />
                                        {t.forgotPassword.backToLogin}
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
