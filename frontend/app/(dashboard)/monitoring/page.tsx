"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts"
import {
    TrendingUp, TrendingDown, Clock, ShieldAlert, Database, Activity,
    AlertTriangle, AlertCircle, CheckCircle2, ExternalLink, RefreshCw,
    Lightbulb, BookOpen, Wrench, Zap,
} from "lucide-react"

type LatencyEntry = { name: string; latence_ms: number; appels: number }
type AlertEntry = { level: "warning" | "critical"; metric: string; message: string; recommendation?: string; value: number; threshold: number }
type KbEvent = { date: string; chunks: number }

type ComponentStatus = {
    name: string
    status: "operational" | "degraded" | "outage" | "unknown"
    uptime: string | null
}

type MistralStatus = {
    overall: "operational" | "degraded" | "outage" | "unknown"
    components: ComponentStatus[]
    fetched_at: string
}

type AiMetrics = {
    total_calls: number
    error_rate: number
    avg_latency_ms: number | null
    avg_rag_chunks: number
    no_context_rate: number
    latency_trend: LatencyEntry[]
    alerts: AlertEntry[]
    model_name: string | null
    kb_events: KbEvent[]
    prev_latency_ms: number | null
    prev_error_rate: number | null
    prev_no_context_rate: number | null
    kb_score: number | null
    negative_rate: number
}

const PERIODS = [
    { label: "7 Jours", days: 7 },
    { label: "30 Jours", days: 30 },
    { label: "90 Jours", days: 90 },
    { label: "Année", days: 365 },
]

function fmtLatency(ms: number | null): string {
    if (ms === null) return "–"
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}

export default function MonitoringPage() {
    const router = useRouter()
    const [days, setDays] = useState(30)
    const [metrics, setMetrics] = useState<AiMetrics | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [mistralStatus, setMistralStatus] = useState<MistralStatus | null>(null)
    const [statusLoading, setStatusLoading] = useState(true)

    const fetchMistralStatus = () => {
        setStatusLoading(true)
        fetch("/api/mistral-status")
            .then(r => r.ok ? r.json() : null)
            .then(data => { if (data) setMistralStatus(data) })
            .catch(() => {})
            .finally(() => setStatusLoading(false))
    }

    const handlePeriodChange = (d: number) => {
        if (d === days) return
        setIsLoading(true)
        setDays(d)
    }

    useEffect(() => {
        fetch("/api/me")
            .then(r => { if (r.status === 401) { router.replace("/login"); return null } return r.ok ? r.json() : null })
            .then(me => { if (me && me.role !== "admin" && me.role !== "sav") router.replace("/dashboard") })
            .catch(() => {})
    }, [router])

    useEffect(() => {
        fetch("/api/mistral-status")
            .then(r => r.ok ? r.json() : null)
            .then(data => { if (data) setMistralStatus(data) })
            .catch(() => {})
            .finally(() => setStatusLoading(false))
    }, [])

    useEffect(() => {
        fetch(`/api/analytics/ai-metrics?days=${days}`)
            .then(r => r.ok ? r.json() : null)
            .then(data => { if (data) setMetrics(data) })
            .catch(() => {})
            .finally(() => setIsLoading(false))
    }, [days])

    const alerts = metrics?.alerts ?? []

    return (
        <div className="flex flex-col min-h-full">
            {/* Header */}
            <div className="p-8 pb-4 bg-background border-b flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Activity className="h-5 w-5 text-indigo-500" />
                        <h1 className="text-2xl font-bold tracking-tight">Monitoring du modèle IA</h1>
                        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">Mistral AI</span>
                        {metrics?.model_name && (
                            <span className="text-xs font-mono bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded-full">
                                {metrics.model_name}
                            </span>
                        )}
                    </div>
                    <p className="text-muted-foreground">Latence, taux d&apos;erreur et qualité RAG du modèle en production.</p>
                </div>
                <div className="flex bg-muted/50 p-1 rounded-lg">
                    {PERIODS.map(({ label, days: d }) => (
                        <Button key={d} onClick={() => handlePeriodChange(d)}
                            variant={days === d ? "secondary" : "ghost"} size="sm"
                            className={`rounded-md ${days === d ? "shadow-sm bg-background text-foreground" : "hover:bg-background text-muted-foreground hover:text-foreground"}`}>
                            {label}
                        </Button>
                    ))}
                </div>
            </div>

            <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">

                {/* Alertes */}
                {!isLoading && (
                    alerts.length > 0 ? (
                        <div className="space-y-2">
                            {alerts.map((alert, i) => (
                                <div key={i} role="alert"
                                    className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${alert.level === "critical" ? "bg-red-50 border-red-200 text-red-800" : "bg-amber-50 border-amber-200 text-amber-800"}`}>
                                    {alert.level === "critical" ? <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" /> : <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />}
                                    <div className="flex-1">
                                        <span className="font-semibold">{alert.level === "critical" ? "Critique" : "Attention"} — </span>
                                        {alert.message}
                                        <span className="ml-2 text-xs opacity-70">
                                            (seuil : {alert.threshold}{alert.metric === "latency" ? "ms" : "%"})
                                        </span>
                                        {alert.recommendation && (
                                            <p className="mt-1 text-xs opacity-80">→ {alert.recommendation}</p>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                            <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                            <span>Toutes les métriques du modèle sont dans les seuils normaux.</span>
                        </div>
                    )
                )}

                {/* KB Score */}
                {!isLoading && metrics && <KbScoreCard score={metrics.kb_score} totalCalls={metrics.total_calls} negativeRate={metrics.negative_rate} />}

                {/* Status Mistral */}
                <MistralStatusCard status={mistralStatus} loading={statusLoading} onRefresh={fetchMistralStatus} />

                {/* KPIs */}
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                    <KpiCard title="Appels totaux"
                        value={isLoading ? "…" : (metrics?.total_calls?.toLocaleString() ?? "0")}
                        trend={`sur ${days} jours`} trendUp={true}
                        icon={<Activity className="h-4 w-4 text-indigo-500" />} />
                    <KpiCard title="Latence moyenne"
                        value={isLoading ? "…" : fmtLatency(metrics?.avg_latency_ms ?? null)}
                        trend={metrics?.total_calls ? `sur ${metrics.total_calls} appels` : "aucune donnée"}
                        trendUp={metrics?.avg_latency_ms == null || metrics.avg_latency_ms < 5000}
                        icon={<Clock className="h-4 w-4 text-blue-500" />}
                        prev={metrics?.prev_latency_ms ?? null}
                        curr={metrics?.avg_latency_ms ?? null}
                        lowerIsBetter />
                    <KpiCard title="Taux d'erreur"
                        value={isLoading ? "…" : `${metrics?.error_rate ?? 0}%`}
                        trend={metrics?.total_calls ? `${metrics.total_calls} appels analysés` : "aucun appel"}
                        trendUp={(metrics?.error_rate ?? 0) <= 5}
                        icon={<ShieldAlert className="h-4 w-4 text-red-400" />}
                        prev={metrics?.prev_error_rate ?? null}
                        curr={metrics?.error_rate ?? null}
                        lowerIsBetter />
                    <KpiCard title="Sans contexte RAG"
                        value={isLoading ? "…" : `${metrics?.no_context_rate ?? 0}%`}
                        trend="requêtes sans résultat KB"
                        trendUp={(metrics?.no_context_rate ?? 0) <= 30}
                        icon={<Database className="h-4 w-4 text-emerald-500" />}
                        prev={metrics?.prev_no_context_rate ?? null}
                        curr={metrics?.no_context_rate ?? null}
                        lowerIsBetter />
                </div>

                {/* Recommandations + Historique */}
                {!isLoading && metrics && (
                    <div className="grid gap-6 lg:grid-cols-2">
                        <RecommendationsCard metrics={metrics} />
                        <ImprovementHistoryCard metrics={metrics} days={days} />
                    </div>
                )}

                {/* Graphique latence + carte sans contexte */}
                <div className="grid gap-6 lg:grid-cols-3">
                    <Card className="lg:col-span-2">
                        <CardHeader>
                            <CardTitle>Évolution de la latence</CardTitle>
                            <CardDescription>
                                Temps moyen de génération par jour (ms) — du premier au dernier token.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {!metrics?.latency_trend?.length ? (
                                <div className="flex flex-col items-center justify-center h-[260px] text-muted-foreground text-sm gap-2">
                                    <Activity className="h-8 w-8 text-slate-200" />
                                    <span>Aucune donnée — les métriques s&apos;accumulent au fil des échanges.</span>
                                </div>
                            ) : (
                                <div className="h-[260px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={metrics.latency_trend} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                            <XAxis dataKey="name" stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} />
                                            <YAxis stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} tickFormatter={v => `${v}ms`} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: "#fff", borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                                                formatter={(value: number | undefined) => [value != null ? `${value}ms` : "–", "Latence"]}
                                            />
                                            <Legend wrapperStyle={{ paddingTop: "12px" }} iconType="circle" />
                                            <Line type="monotone" dataKey="latence_ms" name="Latence (ms)" stroke="#4f46e5" strokeWidth={2} dot={{ r: 3, fill: "#4f46e5" }} activeDot={{ r: 5 }} />
                                            {metrics?.kb_events?.map((e, i) => (
                                                <ReferenceLine key={i} x={e.date} stroke="#10b981" strokeDasharray="4 2"
                                                    label={{ value: "KB+", position: "insideTopRight", fontSize: 10, fill: "#10b981" }} />
                                            ))}
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Qualité RAG */}
                    <div className="space-y-4">
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground">Requêtes sans contexte RAG</CardTitle>
                                <Database className="h-4 w-4 text-amber-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{isLoading ? "…" : `${metrics?.no_context_rate ?? 0}%`}</div>
                                <p className="text-xs text-muted-foreground mt-1">des requêtes sans résultat KB</p>
                                {!isLoading && (metrics?.no_context_rate ?? 0) > 50 && (
                                    <p className="text-xs text-amber-600 mt-2 flex items-center gap-1">
                                        <AlertTriangle className="h-3 w-3" /> Enrichir la base de connaissances
                                    </p>
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground">Seuils configurés</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2 text-xs text-muted-foreground">
                                <div className="flex justify-between"><span>Latence warning</span><span className="font-mono">5 000ms</span></div>
                                <div className="flex justify-between"><span>Latence critique</span><span className="font-mono">10 000ms</span></div>
                                <div className="flex justify-between"><span>Erreurs warning</span><span className="font-mono">5%</span></div>
                                <div className="flex justify-between"><span>Erreurs critique</span><span className="font-mono">15%</span></div>
                                <div className="flex justify-between"><span>Sans contexte</span><span className="font-mono">70%</span></div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    )
}

type KbLevel = { label: string; message: string; color: string; bg: string; border: string; bar: string }

const KB_LEVELS: [number, KbLevel][] = [
    [75, { label: "Excellente", message: "La base de connaissances est bien alimentée. Le modèle dispose d'un contexte riche pour répondre aux questions.",          color: "text-emerald-700", bg: "bg-emerald-50",  border: "border-emerald-200", bar: "bg-emerald-500" }],
    [50, { label: "Correcte",   message: "Quelques lacunes détectées. Enrichir la base de connaissances améliorerait la qualité des réponses de l'IA.",              color: "text-amber-700",   bg: "bg-amber-50",   border: "border-amber-200",   bar: "bg-amber-400"   }],
    [25, { label: "Insuffisante", message: "La base de connaissances manque de contenu. L'IA répond souvent sans contexte — enrichissement recommandé.",             color: "text-orange-700",  bg: "bg-orange-50",  border: "border-orange-200",  bar: "bg-orange-500"  }],
    [0,  { label: "Critique",   message: "La base de connaissances est trop pauvre. Le modèle ne peut pas répondre correctement — enrichissement urgent nécessaire.", color: "text-red-700",     bg: "bg-red-50",     border: "border-red-200",     bar: "bg-red-500"     }],
]

function getKbLevel(score: number): KbLevel {
    for (const [threshold, level] of KB_LEVELS) {
        if (score >= threshold) return level
    }
    return KB_LEVELS[KB_LEVELS.length - 1][1]
}

function KbScoreInfo({ open, onToggle }: { open: boolean; onToggle: () => void }) {
    return (
        <button
            type="button"
            onClick={onToggle}
            className={`inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold cursor-pointer select-none transition-colors ${open ? "bg-slate-700 text-white" : "bg-slate-200 text-slate-500 hover:bg-slate-300"}`}
        >i</button>
    )
}

function KbScoreCard({ score, totalCalls, negativeRate }: { score: number | null; totalCalls: number; negativeRate: number }) {
    const [infoOpen, setInfoOpen] = useState(false)

    if (totalCalls < 5) {
        return (
            <Card className="border-slate-200">
                <CardContent className="py-4 flex items-center gap-3 text-sm text-muted-foreground">
                    <Database className="h-4 w-4 flex-shrink-0" />
                    <span>Score de santé KB indisponible — au moins 5 appels IA nécessaires pour calculer le score (<strong>{totalCalls}</strong> enregistrés).</span>
                </CardContent>
            </Card>
        )
    }

    const s = score ?? 0
    const level = getKbLevel(s)

    return (
        <Card className={`border ${level.border} ${level.bg}`}>
            <CardContent className="py-4">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className="flex-shrink-0">
                            {s >= 75
                                ? <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                                : s >= 50
                                ? <AlertTriangle className="h-5 w-5 text-amber-600" />
                                : <AlertCircle className="h-5 w-5 text-red-600" />}
                        </div>
                        <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-0.5">
                                <span className={`text-sm font-semibold ${level.color}`}>
                                    Base de connaissances — {level.label}
                                </span>
                                <span className={`text-xs font-bold ${level.color}`}>{s}/100</span>
                                <KbScoreInfo open={infoOpen} onToggle={() => setInfoOpen(o => !o)} />
                            </div>
                            <p className={`text-xs ${level.color} opacity-80`}>{level.message}</p>
                            {negativeRate > 0 && (
                                <p className="text-[10px] text-red-500 mt-0.5">👎 {negativeRate}% de pouces rouges sur la période</p>
                            )}
                            {infoOpen && (
                                <div className="mt-3 p-3 bg-slate-900 text-white text-xs rounded-lg space-y-1.5">
                                    <p className="font-semibold mb-2">Comment ce score est-il calculé ?</p>
                                    <div className="flex justify-between gap-2 text-slate-300">
                                        <span>📦 Contexte récupéré (chunks KB trouvés)</span>
                                        <span className="font-bold text-white shrink-0">× 40%</span>
                                    </div>
                                    <div className="flex justify-between gap-2 text-slate-300">
                                        <span>👎 Satisfaction utilisateur (pouces rouges)</span>
                                        <span className="font-bold text-white shrink-0">× 40%</span>
                                    </div>
                                    <div className="flex justify-between gap-2 text-slate-300">
                                        <span>⚙️ Fiabilité technique (taux d&apos;erreur)</span>
                                        <span className="font-bold text-white shrink-0">× 20%</span>
                                    </div>
                                    <p className="mt-2 text-slate-400 text-[10px] pt-1 border-t border-slate-700">Sans retour utilisateur, la satisfaction est considérée parfaite. Le score diminue uniquement en cas de pouce rouge.</p>
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                        <div className="w-32">
                            <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                                <span>Score KB</span><span>{s}%</span>
                            </div>
                            <div className="h-2 w-full rounded-full bg-white/60 border border-white/40 overflow-hidden">
                                <div className={`h-full rounded-full transition-all duration-500 ${level.bar}`} style={{ width: `${s}%` }} />
                            </div>
                        </div>
                        {s < 75 && (
                            <a href="/knowledge-base"
                                className={`text-xs font-semibold px-3 py-1.5 rounded-lg border ${level.border} ${level.color} bg-white/70 hover:bg-white transition-colors whitespace-nowrap`}>
                                Enrichir la KB →
                            </a>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

const STATUS_CONFIG = {
    operational: { label: "Opérationnel", dot: "bg-emerald-500", badge: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    degraded:    { label: "Dégradé",      dot: "bg-amber-500",   badge: "bg-amber-50 text-amber-700 border-amber-200" },
    outage:      { label: "Panne",        dot: "bg-red-500",     badge: "bg-red-50 text-red-700 border-red-200" },
    unknown:     { label: "Inconnu",      dot: "bg-slate-400",   badge: "bg-slate-50 text-slate-600 border-slate-200" },
}

function MistralStatusCard({ status, loading, onRefresh }: { status: MistralStatus | null; loading: boolean; onRefresh: () => void }) {
    const overall = status?.overall ?? "unknown"
    const cfg = STATUS_CONFIG[overall]

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 rounded-full ${cfg.dot} ${overall === "operational" ? "animate-pulse" : ""}`} />
                        <CardTitle className="text-base">Status Mistral AI</CardTitle>
                        <a href="https://status.mistral.ai" target="_blank" rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-foreground transition-colors">
                            <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                    </div>
                    <div className="flex items-center gap-2">
                        {status?.fetched_at && (
                            <span className="text-xs text-muted-foreground">
                                {new Date(status.fetched_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                            </span>
                        )}
                        <button onClick={onRefresh} disabled={loading}
                            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50">
                            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                        </button>
                    </div>
                </div>
                <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${cfg.badge}`}>
                        {loading ? "Chargement…" : cfg.label}
                    </span>
                    <CardDescription className="text-xs">Mis à jour toutes les 60 secondes</CardDescription>
                </div>
            </CardHeader>
            <CardContent>
                {loading ? (
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {[...Array(6)].map((_, i) => (
                            <div key={i} className="h-10 rounded-lg bg-muted animate-pulse" />
                        ))}
                    </div>
                ) : status?.components?.length ? (
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {status.components.map((c) => {
                            const s = STATUS_CONFIG[c.status]
                            return (
                                <div key={c.name} className="flex items-center gap-2 rounded-lg border px-3 py-2 bg-slate-50/50">
                                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${s.dot}`} />
                                    <div className="min-w-0">
                                        <p className="text-xs font-medium truncate">{c.name}</p>
                                        {c.uptime && (
                                            <p className="text-[10px] text-muted-foreground">{c.uptime} uptime</p>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                ) : (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                        <AlertTriangle className="h-4 w-4" />
                        <span>Impossible de récupérer le status. <a href="https://status.mistral.ai" target="_blank" rel="noopener noreferrer" className="underline">Voir directement →</a></span>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

type Reco = { icon: React.ReactNode; title: string; detail: string; action?: { label: string; href: string } }

function buildRecommendations(m: AiMetrics): Reco[] {
    const recos: Reco[] = []

    if (m.no_context_rate > 30) {
        recos.push({
            icon: <BookOpen className="h-4 w-4 text-amber-500" />,
            title: "Enrichir la base de connaissances",
            detail: `${m.no_context_rate}% des questions n'obtiennent aucun contexte RAG. Ajouter des documents couvrant les sujets fréquents réduira les réponses génériques.`,
            action: { label: "Gérer la base de connaissances →", href: "/knowledge-base" },
        })
    }

    if (m.avg_latency_ms !== null && m.avg_latency_ms > 5000) {
        recos.push({
            icon: <Zap className="h-4 w-4 text-yellow-500" />,
            title: "Latence élevée détectée",
            detail: `Latence moyenne de ${m.avg_latency_ms}ms. Envisager de réduire le paramètre KB_MAX_CONTEXT_CHARS pour limiter la taille du prompt envoyé au modèle.`,
        })
    }

    if (m.error_rate > 5) {
        recos.push({
            icon: <Wrench className="h-4 w-4 text-red-500" />,
            title: "Vérifier la configuration de l'API Mistral",
            detail: `Taux d'erreur de ${m.error_rate}%. Vérifier que la clé MISTRAL_API_KEY est valide et que les quotas de l'API ne sont pas atteints.`,
        })
    }

    if (m.avg_rag_chunks < 1 && m.total_calls > 0) {
        recos.push({
            icon: <Database className="h-4 w-4 text-slate-500" />,
            title: "Aucun chunk RAG récupéré en moyenne",
            detail: "Le modèle répond sans contexte issu de la base de connaissances. Vérifier que les embeddings ont bien été générés lors de l'ingestion des documents.",
            action: { label: "Gérer la base de connaissances →", href: "/knowledge-base" },
        })
    }

    if (recos.length === 0) {
        recos.push({
            icon: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
            title: "Modèle en bonne santé",
            detail: "Toutes les métriques sont dans les seuils acceptables. Continuer à collecter du feedback utilisateur pour affiner la base de connaissances.",
        })
    }

    return recos
}

function RecommendationsCard({ metrics }: { metrics: AiMetrics }) {
    const recos = buildRecommendations(metrics)
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-yellow-500" />
                    <CardTitle className="text-base">Recommandations d&apos;amélioration</CardTitle>
                </div>
                <CardDescription>Actions concrètes basées sur les métriques actuelles pour améliorer le modèle de façon itérative.</CardDescription>
            </CardHeader>
            <CardContent>
                <div className="space-y-3">
                    {recos.map((r, i) => (
                        <div key={i} className="flex items-start gap-3 rounded-lg border px-4 py-3 bg-slate-50/50">
                            <div className="mt-0.5 flex-shrink-0">{r.icon}</div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium">{r.title}</p>
                                <p className="text-xs text-muted-foreground mt-0.5">{r.detail}</p>
                                {r.action && (
                                    <a href={r.action.href} className="text-xs text-indigo-600 hover:text-indigo-800 font-medium mt-1 inline-block">
                                        {r.action.label}
                                    </a>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    )
}

function DeltaBadge({ curr, prev, lowerIsBetter }: { curr: number | null; prev: number | null; lowerIsBetter?: boolean }) {
    if (curr === null || prev === null || prev === 0) return null
    const pct = Math.round(((curr - prev) / prev) * 100)
    if (pct === 0) return null
    const improved = lowerIsBetter ? pct < 0 : pct > 0
    return (
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ml-2 ${improved ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
            {pct > 0 ? "+" : ""}{pct}% vs préc.
        </span>
    )
}

function KpiCard({ title, value, trend, trendUp, icon, curr, prev, lowerIsBetter }: {
    title: string; value: string; trend: string; trendUp: boolean; icon: React.ReactNode
    curr?: number | null; prev?: number | null; lowerIsBetter?: boolean
}) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
                {icon}
            </CardHeader>
            <CardContent>
                <div className="flex items-baseline">
                    <span className="text-2xl font-bold">{value}</span>
                    <DeltaBadge curr={curr ?? null} prev={prev ?? null} lowerIsBetter={lowerIsBetter} />
                </div>
                <p className="text-xs text-muted-foreground flex items-center mt-1">
                    {trendUp ? <TrendingUp className="h-3 w-3 text-green-500 mr-1" /> : <TrendingDown className="h-3 w-3 text-red-500 mr-1" />}
                    <span className="ml-1">{trend}</span>
                </p>
            </CardContent>
        </Card>
    )
}

function ImprovementHistoryCard({ metrics, days }: { metrics: AiMetrics; days: number }) {
    const hasKbEvents = metrics.kb_events?.length > 0
    const hasPrev = metrics.prev_latency_ms !== null || metrics.prev_error_rate !== null || metrics.prev_no_context_rate !== null

    const deltas: { label: string; prev: number | null; curr: number | null; unit: string; lowerIsBetter: boolean }[] = [
        { label: "Latence", prev: metrics.prev_latency_ms, curr: metrics.avg_latency_ms, unit: "ms", lowerIsBetter: true },
        { label: "Taux d'erreur", prev: metrics.prev_error_rate, curr: metrics.error_rate, unit: "%", lowerIsBetter: true },
        { label: "Sans contexte", prev: metrics.prev_no_context_rate, curr: metrics.no_context_rate, unit: "%", lowerIsBetter: true },
    ]

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-indigo-500" />
                    <CardTitle className="text-base">Historique des améliorations</CardTitle>
                </div>
                <CardDescription>Boucle itérative : enrichissements KB et impact sur les métriques.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* KB events timeline */}
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Enrichissements KB sur {days} jours</p>
                    {hasKbEvents ? (
                        <div className="space-y-1.5">
                            {metrics.kb_events.map((e, i) => (
                                <div key={i} className="flex items-center gap-2 text-sm">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
                                    <span className="font-mono text-xs text-muted-foreground w-12">{e.date}</span>
                                    <span className="text-xs">{e.chunks} chunks ajoutés à la base de connaissances</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground italic">Aucun enrichissement sur cette période.</p>
                    )}
                </div>

                {/* Period comparison */}
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Impact mesuré (vs {days} jours précédents)</p>
                    {hasPrev ? (
                        <div className="space-y-2">
                            {deltas.filter(d => d.prev !== null && d.curr !== null).map((d, i) => {
                                const pct = d.prev && d.prev > 0 ? Math.round(((d.curr! - d.prev) / d.prev) * 100) : null
                                const improved = pct !== null && (d.lowerIsBetter ? pct < 0 : pct > 0)
                                return (
                                    <div key={i} className="flex items-center justify-between text-xs">
                                        <span className="text-muted-foreground">{d.label}</span>
                                        <div className="flex items-center gap-2">
                                            <span className="text-muted-foreground">{d.prev}{d.unit}</span>
                                            <span className="text-muted-foreground">→</span>
                                            <span className="font-medium">{d.curr}{d.unit}</span>
                                            {pct !== null && pct !== 0 && (
                                                <span className={`font-semibold ${improved ? "text-emerald-600" : "text-red-600"}`}>
                                                    ({pct > 0 ? "+" : ""}{pct}%)
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground italic">Pas assez de données sur la période précédente.</p>
                    )}
                </div>
            </CardContent>
        </Card>
    )
}
