"use client"

import Image from "next/image"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { LanguageToggle } from "@/components/LanguageToggle"
import { useLocale } from "@/lib/i18n/LocaleContext"
import { BRAND_NAME } from "@/lib/brand"

export default function NotFoundContent() {
    const { messages: t } = useLocale()
    return (
        <div className="force-light min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/40 to-white flex flex-col">
            <header className="p-6 flex items-center justify-between">
                <Link href="/" className="flex items-center">
                    <Image src="/logo-Tiqia-noir.png" alt={BRAND_NAME} width={77} height={32} className="h-8 w-auto" />
                </Link>
                <LanguageToggle />
            </header>

            <div className="flex-1 flex items-center justify-center px-6 py-12">
                <div className="text-center max-w-md">
                    <Image src="/logo-T.png" alt={BRAND_NAME} width={64} height={64} className="w-16 h-16 mx-auto mb-6" />
                    <p className="text-6xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600 mb-4">
                        404
                    </p>
                    <h1 className="text-2xl font-bold text-slate-900 mb-2">{t.notFound.title}</h1>
                    <p className="text-slate-500 mb-8">{t.notFound.subtitle}</p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                        <Button size="lg" className="bg-indigo-600 hover:bg-indigo-700 text-white" asChild>
                            <Link href="/">
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                {t.notFound.backHome}
                            </Link>
                        </Button>
                        <Button size="lg" variant="outline" asChild>
                            <Link href="/login">{t.notFound.backLogin}</Link>
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}
