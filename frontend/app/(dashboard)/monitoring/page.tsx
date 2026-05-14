"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts"
import {
    TrendingUp, TrendingDown, Clock, ShieldAlert, Database, Activity,
    AlertTriangle, AlertCircle, CheckCircle2, ExternalLink, RefreshCw,
} from "lucide-react"

type LatencyEntry = { name: string; latence_ms: number; appels: number }
type AlertEntry = { level: "warning" | "critical"; metric: string; message: string; value: number; threshold: number }

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

    useEffect(() => {
        fetch("/api/me")
            .then(r => { if (r.status === 401) { router.replace("/login"); return null } return r.ok ? r.json() : null })
            .then(me => { if (me && me.role !== "admin" && me.role !== "sav") router.replace("/") })
            .catch(() => {})
    }, [router])

    useEffect(() => { fetchMistralStatus() }, [])

    useEffect(() => {
        setIsLoading(true)
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
                    </div>
                    <p className="text-muted-foreground">Latence, taux d&apos;erreur et qualité RAG du modèle en production.</p>
                </div>
                <div className="flex bg-muted/50 p-1 rounded-lg">
                    {PERIODS.map(({ label, days: d }) => (
                        <Button key={d} onClick={() => { if (d !== days) { setIsLoading(true); setDays(d) } }}
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
                        icon={<Clock className="h-4 w-4 text-blue-500" />} />
                    <KpiCard title="Taux d'erreur"
                        value={isLoading ? "…" : `${metrics?.error_rate ?? 0}%`}
                        trend={metrics?.total_calls ? `${metrics.total_calls} appels analysés` : "aucun appel"}
                        trendUp={(metrics?.error_rate ?? 0) <= 5}
                        icon={<ShieldAlert className="h-4 w-4 text-red-400" />} />
                    <KpiCard title="Chunks RAG moyens"
                        value={isLoading ? "…" : `${metrics?.avg_rag_chunks ?? 0}`}
                        trend="extraits de la base de connaissances"
                        trendUp={(metrics?.avg_rag_chunks ?? 0) > 0}
                        icon={<Database className="h-4 w-4 text-emerald-500" />} />
                </div>

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

function KpiCard({ title, value, trend, trendUp, icon }: { title: string; value: string; trend: string; trendUp: boolean; icon: React.ReactNode }) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
                {icon}
            </CardHeader>
            <CardContent>
                <div className="text-2xl font-bold">{value}</div>
                <p className="text-xs text-muted-foreground flex items-center mt-1">
                    {trendUp ? <TrendingUp className="h-3 w-3 text-green-500 mr-1" /> : <TrendingDown className="h-3 w-3 text-red-500 mr-1" />}
                    <span className="ml-1">{trend}</span>
                </p>
            </CardContent>
        </Card>
    )
}
