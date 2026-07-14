"use client"

import Image from "next/image"
import Link from "next/link"
import { useLocale } from "@/lib/i18n/LocaleContext"
import { LanguageToggle } from "@/components/LanguageToggle"

export default function LegalLayout({ children }: { children: React.ReactNode }) {
    const { messages: t } = useLocale()
    return (
        <div className="force-light min-h-screen bg-white flex flex-col">
            <header className="border-b border-slate-100 px-6 py-4">
                <div className="max-w-3xl mx-auto flex items-center justify-between gap-4">
                    <Link href="/" className="flex items-center gap-2 text-slate-700">
                        <Image src="/logo_smartticket.png" alt="SmartTicket" width={24} height={24} className="h-6 w-6" />
                        <span className="font-semibold">SmartTicket</span>
                    </Link>
                    <div className="flex items-center gap-4">
                        <LanguageToggle />
                        <Link href="/" className="text-sm text-indigo-600 hover:underline">
                            {t.legal.backToHome}
                        </Link>
                    </div>
                </div>
            </header>
            <main className="flex-1 px-6 py-12">
                <div className="max-w-3xl mx-auto space-y-8 text-slate-700 text-sm leading-relaxed">
                    {children}
                </div>
            </main>
        </div>
    )
}
