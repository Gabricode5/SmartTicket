"use client"

import Image from "next/image"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { LanguageToggle } from "@/components/LanguageToggle"
import { useLocale } from "@/lib/i18n/LocaleContext"
import {
    MessageSquare, Zap, BookOpen, BarChart2, ArrowRight,
    ShieldCheck, Users, Activity, CheckCircle2, Building2,
    Lock, TrendingUp, Headset,
} from "lucide-react"

const FEATURE_ICONS = [
    <MessageSquare key="assistant" className="h-5 w-5 text-indigo-600" />,
    <BookOpen key="rag" className="h-5 w-5 text-violet-600" />,
    <Users key="escalation" className="h-5 w-5 text-emerald-600" />,
    <BarChart2 key="analytics" className="h-5 w-5 text-amber-600" />,
    <Activity key="monitoring" className="h-5 w-5 text-blue-600" />,
    <ShieldCheck key="security" className="h-5 w-5 text-slate-600" />,
]
const FEATURE_BG = ["bg-indigo-50", "bg-violet-50", "bg-emerald-50", "bg-amber-50", "bg-blue-50", "bg-slate-100"]

const STEP_COLORS = [
    "text-indigo-600 bg-indigo-50 border-indigo-100",
    "text-violet-600 bg-violet-50 border-violet-100",
    "text-emerald-600 bg-emerald-50 border-emerald-100",
]

const ENTERPRISE_ICONS = [
    <Lock key="security" className="h-5 w-5 text-indigo-600" />,
    <TrendingUp key="scale" className="h-5 w-5 text-violet-600" />,
    <Users key="teams" className="h-5 w-5 text-emerald-600" />,
    <Headset key="support" className="h-5 w-5 text-amber-600" />,
]
const ENTERPRISE_BG = ["bg-indigo-50", "bg-violet-50", "bg-emerald-50", "bg-amber-50"]

export default function LandingPage() {
    const { messages: t } = useLocale()
    return (
        <div className="force-light min-h-screen bg-white flex flex-col">

            {/* ── Navbar ── */}
            <header className="sticky top-0 z-50 border-b border-slate-100 bg-white/80 backdrop-blur-sm">
                <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2 font-bold text-xl">
                        <Image src="/logo_smartticket.png" alt="SmartTicket" width={32} height={32} className="h-8 w-8" priority />
                        <span className="text-slate-900">SmartTicket</span>
                    </div>
                    <nav className="hidden md:flex items-center gap-8 text-sm text-slate-600">
                        <a href="#features" className="hover:text-indigo-600 transition-colors">{t.landing.nav.features}</a>
                        <a href="#how" className="hover:text-indigo-600 transition-colors">{t.landing.nav.how}</a>
                        <a href="#entreprises" className="hover:text-indigo-600 transition-colors">{t.landing.nav.entreprises}</a>
                    </nav>
                    <div className="flex items-center gap-3">
                        <LanguageToggle className="hidden sm:inline-flex" />
                        <Button variant="ghost" size="sm" asChild>
                            <Link href="/login">{t.landing.nav.login}</Link>
                        </Button>
                        <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white" asChild>
                            <Link href="/sign-up">{t.landing.nav.tryFree}</Link>
                        </Button>
                    </div>
                </div>
            </header>

            {/* ── Hero ── */}
            <section className="relative overflow-hidden bg-gradient-to-br from-slate-50 via-indigo-50/30 to-white pt-20 pb-24 px-6">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-100/40 via-transparent to-transparent pointer-events-none" />
                <div className="max-w-4xl mx-auto text-center relative">
                    <span className="inline-flex items-center gap-2 text-xs font-semibold text-indigo-600 bg-indigo-50 border border-indigo-100 px-3 py-1.5 rounded-full mb-6">
                        <Zap className="h-3 w-3" />
                        {t.landing.hero.badge}
                    </span>
                    <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 tracking-tight leading-tight mb-6">
                        {t.landing.hero.titleStart}{" "}
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600">
                            {t.landing.hero.titleHighlight}
                        </span>
                        <br />{t.landing.hero.titleEnd}
                    </h1>
                    <p className="text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed">
                        {t.landing.hero.subtitle}
                    </p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Button size="lg" className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 h-12 text-base" asChild>
                            <Link href="/sign-up">
                                {t.landing.hero.ctaPrimary}
                                <ArrowRight className="ml-2 h-4 w-4" />
                            </Link>
                        </Button>
                        <Button size="lg" variant="outline" className="h-12 px-8 text-base border-slate-200" asChild>
                            <Link href="/login">{t.landing.hero.ctaSecondary}</Link>
                        </Button>
                    </div>
                    <p className="mt-5 text-sm text-slate-400">
                        {t.landing.hero.guestPrompt}{" "}
                        <Link href="/chat" className="text-indigo-600 font-medium hover:underline">
                            {t.landing.hero.guestLink}
                        </Link>
                    </p>
                </div>

                {/* Preview card */}
                <div className="max-w-2xl mx-auto mt-16 relative">
                    <div className="rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-indigo-100 overflow-hidden">
                        <div className="bg-slate-50 border-b border-slate-100 px-4 py-3 flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full bg-red-400" />
                            <div className="w-3 h-3 rounded-full bg-amber-400" />
                            <div className="w-3 h-3 rounded-full bg-emerald-400" />
                            <span className="ml-2 text-xs text-slate-400 font-mono">{t.landing.hero.previewTitle}</span>
                        </div>
                        <div className="p-6 space-y-4">
                            <div className="flex justify-end">
                                <div className="bg-indigo-600 text-white text-sm rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-xs">
                                    {t.landing.hero.previewQuestion}
                                </div>
                            </div>
                            <div className="flex items-start gap-3">
                                <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                                    <Zap className="h-3.5 w-3.5 text-indigo-600" />
                                </div>
                                <div className="bg-slate-50 border border-slate-100 text-slate-700 text-sm rounded-2xl rounded-tl-sm px-4 py-2.5 max-w-sm leading-relaxed">
                                    {t.landing.hero.previewAnswer}
                                </div>
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                <span className="text-xs text-slate-400">{t.landing.hero.previewActive}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ── Stats ── */}
            <section className="border-y border-slate-100 bg-slate-50/50 py-12 px-6">
                <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
                    {t.landing.stats.map((stat) => (
                        <div key={stat.label}>
                            <div className="text-3xl font-extrabold text-indigo-600 mb-1">{stat.value}</div>
                            <div className="text-sm text-slate-500">{stat.label}</div>
                        </div>
                    ))}
                </div>
            </section>

            {/* ── Features ── */}
            <section id="features" className="py-24 px-6">
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
                            {t.landing.features.title}
                        </h2>
                        <p className="text-slate-500 text-lg max-w-2xl mx-auto">
                            {t.landing.features.subtitle}
                        </p>
                    </div>
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {t.landing.features.items.map((f, i) => (
                            <div key={f.title} className="rounded-2xl border border-slate-100 bg-white p-6 hover:shadow-md hover:border-slate-200 transition-all">
                                <div className={`w-10 h-10 rounded-xl ${FEATURE_BG[i]} flex items-center justify-center mb-4`}>
                                    {FEATURE_ICONS[i]}
                                </div>
                                <h3 className="font-semibold text-slate-900 mb-2">{f.title}</h3>
                                <p className="text-sm text-slate-500 leading-relaxed">{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── How it works ── */}
            <section id="how" className="py-24 px-6 bg-slate-50/50 border-y border-slate-100">
                <div className="max-w-4xl mx-auto">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
                            {t.landing.how.title}
                        </h2>
                        <p className="text-slate-500 text-lg">{t.landing.how.subtitle}</p>
                    </div>
                    <div className="grid md:grid-cols-3 gap-8">
                        {t.landing.how.steps.map((s, i) => (
                            <div key={s.title} className="text-center">
                                <div className={`w-14 h-14 rounded-2xl border ${STEP_COLORS[i]} flex items-center justify-center mx-auto mb-5 text-xl font-extrabold`}>
                                    {String(i + 1).padStart(2, "0")}
                                </div>
                                <h3 className="font-semibold text-slate-900 mb-2">{s.title}</h3>
                                <p className="text-sm text-slate-500 leading-relaxed">{s.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── Entreprises ── */}
            <section id="entreprises" className="py-24 px-6 bg-slate-50/50 border-y border-slate-100">
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-16">
                        <span className="inline-flex items-center gap-2 text-xs font-semibold text-indigo-600 bg-indigo-50 border border-indigo-100 px-3 py-1.5 rounded-full mb-6">
                            <Building2 className="h-3 w-3" />
                            {t.landing.enterprise.badge}
                        </span>
                        <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
                            {t.landing.enterprise.title}
                        </h2>
                        <p className="text-slate-500 text-lg max-w-2xl mx-auto">
                            {t.landing.enterprise.subtitle}
                        </p>
                    </div>
                    <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                        {t.landing.enterprise.items.map((f, i) => (
                            <div key={f.title} className="rounded-2xl border border-slate-100 bg-white p-6 hover:shadow-md hover:border-slate-200 transition-all">
                                <div className={`w-10 h-10 rounded-xl ${ENTERPRISE_BG[i]} flex items-center justify-center mb-4`}>
                                    {ENTERPRISE_ICONS[i]}
                                </div>
                                <h3 className="font-semibold text-slate-900 mb-2">{f.title}</h3>
                                <p className="text-sm text-slate-500 leading-relaxed">{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── CTA final ── */}
            <section className="py-24 px-6 bg-gradient-to-br from-indigo-600 to-violet-600">
                <div className="max-w-2xl mx-auto text-center">
                    <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                        {t.landing.cta.title}
                    </h2>
                    <p className="text-indigo-100 mb-8 text-lg">
                        {t.landing.cta.subtitle}
                    </p>
                    <div className="flex flex-col sm:flex-row gap-4 justify-center">
                        <Button size="lg" className="bg-white text-indigo-600 hover:bg-indigo-50 h-12 px-8 text-base font-semibold" asChild>
                            <Link href="/sign-up">
                                {t.landing.cta.primary}
                                <ArrowRight className="ml-2 h-4 w-4" />
                            </Link>
                        </Button>
                        <Button size="lg" variant="outline" className="bg-transparent border-white/40 text-white hover:bg-white/10 h-12 px-8 text-base" asChild>
                            <Link href="/login">{t.landing.cta.secondary}</Link>
                        </Button>
                    </div>
                </div>
            </section>

            {/* ── Footer ── */}
            <footer className="border-t border-slate-100 py-8 px-6 bg-white">
                <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-2 text-slate-600">
                        <Image src="/logo_smartticket.png" alt="SmartTicket" width={24} height={24} className="h-6 w-6" />
                        <span className="font-semibold">SmartTicket</span>
                        <span className="text-slate-400 text-sm ml-2">{t.landing.footer.tagline}</span>
                    </div>
                    <nav className="flex items-center gap-4 text-xs text-slate-400">
                        <Link href="/mentions-legales" className="hover:text-slate-600 hover:underline">{t.landing.footer.legal}</Link>
                        <Link href="/politique-confidentialite" className="hover:text-slate-600 hover:underline">{t.landing.footer.privacy}</Link>
                        <Link href="/cgv" className="hover:text-slate-600 hover:underline">{t.landing.footer.cgv}</Link>
                    </nav>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        {t.landing.footer.poweredBy}
                    </div>
                </div>
            </footer>
        </div>
    )
}
