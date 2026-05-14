import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
    MessageSquare, Zap, BookOpen, BarChart2, ArrowRight,
    ShieldCheck, Users, Activity, CheckCircle2,
} from "lucide-react"

export default function LandingPage() {
    return (
        <div className="min-h-screen bg-white flex flex-col">

            {/* ── Navbar ── */}
            <header className="sticky top-0 z-50 border-b border-slate-100 bg-white/80 backdrop-blur-sm">
                <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2 font-bold text-xl">
                        <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-sm font-bold">
                            A
                        </div>
                        <span className="text-slate-900">SmartTicket</span>
                    </div>
                    <nav className="hidden md:flex items-center gap-8 text-sm text-slate-600">
                        <a href="#features" className="hover:text-indigo-600 transition-colors">Fonctionnalités</a>
                        <a href="#how" className="hover:text-indigo-600 transition-colors">Comment ça marche</a>
                        <a href="#tech" className="hover:text-indigo-600 transition-colors">Technologie</a>
                    </nav>
                    <div className="flex items-center gap-3">
                        <Button variant="ghost" size="sm" asChild>
                            <Link href="/login">Se connecter</Link>
                        </Button>
                        <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white" asChild>
                            <Link href="/sign-up">Essayer gratuitement</Link>
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
                        Propulsé par Mistral AI
                    </span>
                    <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 tracking-tight leading-tight mb-6">
                        Le support client{" "}
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600">
                            intelligent
                        </span>
                        <br />propulsé par l&apos;IA
                    </h1>
                    <p className="text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed">
                        SmartTicket combine l&apos;intelligence artificielle et votre expertise métier
                        pour résoudre les demandes clients plus rapidement — et escalader intelligemment
                        vers vos agents SAV quand nécessaire.
                    </p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Button size="lg" className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 h-12 text-base" asChild>
                            <Link href="/sign-up">
                                Commencer gratuitement
                                <ArrowRight className="ml-2 h-4 w-4" />
                            </Link>
                        </Button>
                        <Button size="lg" variant="outline" className="h-12 px-8 text-base border-slate-200" asChild>
                            <Link href="/login">J&apos;ai déjà un compte</Link>
                        </Button>
                    </div>
                </div>

                {/* Preview card */}
                <div className="max-w-2xl mx-auto mt-16 relative">
                    <div className="rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-indigo-100 overflow-hidden">
                        <div className="bg-slate-50 border-b border-slate-100 px-4 py-3 flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full bg-red-400" />
                            <div className="w-3 h-3 rounded-full bg-amber-400" />
                            <div className="w-3 h-3 rounded-full bg-emerald-400" />
                            <span className="ml-2 text-xs text-slate-400 font-mono">smartticket — assistant IA</span>
                        </div>
                        <div className="p-6 space-y-4">
                            <div className="flex justify-end">
                                <div className="bg-indigo-600 text-white text-sm rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-xs">
                                    Comment puis-je suivre ma commande ?
                                </div>
                            </div>
                            <div className="flex items-start gap-3">
                                <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                                    <Zap className="h-3.5 w-3.5 text-indigo-600" />
                                </div>
                                <div className="bg-slate-50 border border-slate-100 text-slate-700 text-sm rounded-2xl rounded-tl-sm px-4 py-2.5 max-w-sm leading-relaxed">
                                    Vous pouvez suivre votre commande depuis votre espace client, rubrique &quot;Mes commandes&quot;. Un email de suivi vous a également été envoyé à la validation de votre achat.
                                </div>
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                <span className="text-xs text-slate-400">Assistant IA Actif</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ── Stats ── */}
            <section className="border-y border-slate-100 bg-slate-50/50 py-12 px-6">
                <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
                    {[
                        { value: "< 2s", label: "Temps de réponse moyen" },
                        { value: "70%+", label: "Résolution automatique" },
                        { value: "24/7", label: "Disponibilité" },
                        { value: "RAG", label: "Contexte métier intégré" },
                    ].map((stat) => (
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
                            Tout ce qu&apos;il faut pour un support client moderne
                        </h2>
                        <p className="text-slate-500 text-lg max-w-2xl mx-auto">
                            Une plateforme complète qui combine IA générative, base de connaissances
                            et gestion humaine des cas complexes.
                        </p>
                    </div>
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {[
                            {
                                icon: <MessageSquare className="h-5 w-5 text-indigo-600" />,
                                title: "Assistant IA conversationnel",
                                desc: "Répond instantanément aux questions des clients en s'appuyant sur votre base de connaissances métier.",
                                bg: "bg-indigo-50",
                            },
                            {
                                icon: <BookOpen className="h-5 w-5 text-violet-600" />,
                                title: "Base de connaissances RAG",
                                desc: "Ingérez vos documents PDF, pages web et FAQ. L'IA les utilise pour des réponses précises et contextuelles.",
                                bg: "bg-violet-50",
                            },
                            {
                                icon: <Users className="h-5 w-5 text-emerald-600" />,
                                title: "Escalade intelligente vers SAV",
                                desc: "Quand l'IA détecte une question complexe ou sensible, elle transfère vers un agent humain avec le contexte complet.",
                                bg: "bg-emerald-50",
                            },
                            {
                                icon: <BarChart2 className="h-5 w-5 text-amber-600" />,
                                title: "Analytics en temps réel",
                                desc: "Suivez le taux de résolution IA, la satisfaction client, les raisons de transfert et la performance de vos agents.",
                                bg: "bg-amber-50",
                            },
                            {
                                icon: <Activity className="h-5 w-5 text-blue-600" />,
                                title: "Monitoring du modèle IA",
                                desc: "Latence, taux d'erreur, qualité RAG et score de santé de la base de connaissances — tout en un seul endroit.",
                                bg: "bg-blue-50",
                            },
                            {
                                icon: <ShieldCheck className="h-5 w-5 text-slate-600" />,
                                title: "Sécurité & rôles",
                                desc: "Gestion des accès par rôle : utilisateur, agent SAV et administrateur. Sessions chiffrées avec JWT.",
                                bg: "bg-slate-100",
                            },
                        ].map((f) => (
                            <div key={f.title} className="rounded-2xl border border-slate-100 bg-white p-6 hover:shadow-md hover:border-slate-200 transition-all">
                                <div className={`w-10 h-10 rounded-xl ${f.bg} flex items-center justify-center mb-4`}>
                                    {f.icon}
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
                            Comment ça marche
                        </h2>
                        <p className="text-slate-500 text-lg">En 3 étapes simples</p>
                    </div>
                    <div className="grid md:grid-cols-3 gap-8">
                        {[
                            {
                                step: "01",
                                title: "Alimentez la base de connaissances",
                                desc: "Importez vos documents PDF, FAQ et pages web. L'IA les transforme en contexte interrogeable.",
                                color: "text-indigo-600 bg-indigo-50 border-indigo-100",
                            },
                            {
                                step: "02",
                                title: "L'IA répond automatiquement",
                                desc: "Vos clients posent leurs questions. L'assistant IA répond en temps réel en s'appuyant sur vos documents.",
                                color: "text-violet-600 bg-violet-50 border-violet-100",
                            },
                            {
                                step: "03",
                                title: "Vos agents traitent le reste",
                                desc: "Les cas complexes sont transférés à vos agents SAV avec le contexte de la conversation déjà disponible.",
                                color: "text-emerald-600 bg-emerald-50 border-emerald-100",
                            },
                        ].map((s) => (
                            <div key={s.step} className="text-center">
                                <div className={`w-14 h-14 rounded-2xl border ${s.color} flex items-center justify-center mx-auto mb-5 text-xl font-extrabold`}>
                                    {s.step}
                                </div>
                                <h3 className="font-semibold text-slate-900 mb-2">{s.title}</h3>
                                <p className="text-sm text-slate-500 leading-relaxed">{s.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── Tech stack ── */}
            <section id="tech" className="py-24 px-6">
                <div className="max-w-4xl mx-auto text-center">
                    <h2 className="text-3xl font-bold text-slate-900 mb-4">Construit sur des technologies modernes</h2>
                    <p className="text-slate-500 mb-12">Stack open-source, déployé sur Render, modèle Mistral AI.</p>
                    <div className="flex flex-wrap justify-center gap-3">
                        {["Next.js 15", "FastAPI", "PostgreSQL", "pgvector", "Mistral AI", "Docker", "GitHub Actions"].map((tech) => (
                            <span key={tech} className="px-4 py-2 rounded-full border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:border-indigo-300 hover:text-indigo-600 transition-colors">
                                {tech}
                            </span>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── CTA final ── */}
            <section className="py-24 px-6 bg-gradient-to-br from-indigo-600 to-violet-600">
                <div className="max-w-2xl mx-auto text-center">
                    <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                        Prêt à transformer votre support client ?
                    </h2>
                    <p className="text-indigo-100 mb-8 text-lg">
                        Créez votre compte gratuitement et commencez à utiliser l&apos;IA pour votre SAV.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-4 justify-center">
                        <Button size="lg" className="bg-white text-indigo-600 hover:bg-indigo-50 h-12 px-8 text-base font-semibold" asChild>
                            <Link href="/sign-up">
                                Créer un compte gratuit
                                <ArrowRight className="ml-2 h-4 w-4" />
                            </Link>
                        </Button>
                        <Button size="lg" variant="outline" className="border-white/40 text-white hover:bg-white/10 h-12 px-8 text-base" asChild>
                            <Link href="/login">Se connecter</Link>
                        </Button>
                    </div>
                </div>
            </section>

            {/* ── Footer ── */}
            <footer className="border-t border-slate-100 py-8 px-6 bg-white">
                <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-2 text-slate-600">
                        <div className="h-6 w-6 rounded-md bg-indigo-600 flex items-center justify-center text-white text-xs font-bold">A</div>
                        <span className="font-semibold">SmartTicket</span>
                        <span className="text-slate-400 text-sm ml-2">— Support client intelligent</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        Propulsé par Mistral AI
                    </div>
                </div>
            </footer>
        </div>
    )
}
