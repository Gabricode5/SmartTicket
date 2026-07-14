"use client"

import { Suspense, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import Image from "next/image"
import Link from "next/link"
import { ArrowLeft, CheckCircle2, XCircle, Loader2 } from "lucide-react"
import { useLocale } from "@/lib/i18n/LocaleContext"

type Status = "loading" | "success" | "error"

function VerifyEmailContent() {
    const searchParams = useSearchParams()
    const token = searchParams.get("token")
    const { messages: t } = useLocale()

    const [status, setStatus] = useState<Status>("loading")
    const [errorMessage, setErrorMessage] = useState("")
    const [resendEmail, setResendEmail] = useState("")
    const [resendSent, setResendSent] = useState(false)
    const [isResending, setIsResending] = useState(false)

    useEffect(() => {
        if (!token) {
            setStatus("error")
            setErrorMessage(t.verifyEmail.invalidToken)
            return
        }
        fetch(`/api/verify-email?token=${encodeURIComponent(token)}`)
            .then(async (response) => {
                if (response.ok) {
                    setStatus("success")
                } else {
                    const data = await response.json().catch(() => ({}))
                    setStatus("error")
                    setErrorMessage(typeof data.detail === "string" ? data.detail : t.verifyEmail.invalidOrExpiredToken)
                }
            })
            .catch(() => {
                setStatus("error")
                setErrorMessage(t.verifyEmail.networkError)
            })
        // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit se relancer que si le token change, pas au changement de langue
    }, [token])

    async function handleResend(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setIsResending(true)
        try {
            await fetch("/api/resend-verification", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: resendEmail }),
            })
            setResendSent(true)
        } catch {
            // Message générique affiché quoi qu'il arrive, cf. backend (anti-enumération).
            setResendSent(true)
        } finally {
            setIsResending(false)
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
                    <div className="bg-white rounded-2xl shadow-xl shadow-indigo-100/50 border border-slate-100 p-8 text-center">
                        {status === "loading" && (
                            <>
                                <Loader2 className="h-12 w-12 text-indigo-600 mx-auto mb-4 animate-spin" />
                                <h1 className="text-xl font-bold text-slate-900">{t.verifyEmail.verifying}</h1>
                            </>
                        )}

                        {status === "success" && (
                            <>
                                <CheckCircle2 className="h-12 w-12 text-emerald-600 mx-auto mb-4" />
                                <h1 className="text-xl font-bold text-slate-900">{t.verifyEmail.successTitle}</h1>
                                <p className="text-slate-500 text-sm mt-2 mb-6">
                                    {t.verifyEmail.successBody}
                                </p>
                                <Link
                                    href="/login"
                                    className="inline-block w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl transition-colors"
                                >
                                    {t.verifyEmail.login}
                                </Link>
                            </>
                        )}

                        {status === "error" && (
                            <>
                                <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                                <h1 className="text-xl font-bold text-slate-900">{t.verifyEmail.invalidLinkTitle}</h1>
                                <p className="text-slate-500 text-sm mt-2 mb-6">{errorMessage}</p>

                                {resendSent ? (
                                    <p className="text-sm text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-xl p-3">
                                        {t.verifyEmail.resendSentMessage}
                                    </p>
                                ) : (
                                    <form onSubmit={handleResend} className="space-y-3 text-left">
                                        <label htmlFor="resend-email" className="block text-sm font-medium text-slate-700">
                                            {t.verifyEmail.receiveNewLink}
                                        </label>
                                        <input
                                            id="resend-email"
                                            type="email"
                                            required
                                            value={resendEmail}
                                            onChange={(e) => setResendEmail(e.target.value)}
                                            placeholder="vous@exemple.com"
                                            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white transition-all"
                                        />
                                        <button
                                            type="submit"
                                            disabled={isResending}
                                            className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-semibold text-sm rounded-xl transition-colors"
                                        >
                                            {isResending ? t.verifyEmail.resending : t.verifyEmail.resendLink}
                                        </button>
                                    </form>
                                )}
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default function VerifyEmailPage() {
    return (
        <Suspense fallback={null}>
            <VerifyEmailContent />
        </Suspense>
    )
}
