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
    Lightbulb, BookOpen, Wrench, Zap, Download, FileText,
} from "lucide-react"
import { downloadCsv } from "@/lib/csv"
import { useLocale } from "@/lib/i18n/LocaleContext"
import type { Messages } from "@/lib/i18n/translations"

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

function fmtLatency(ms: number | null): string {
    if (ms === null) return "–"
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}

export default function MonitoringPage() {
    const router = useRouter()
    const { messages: t, locale } = useLocale()
    const timeLocale = locale === "fr" ? "fr-FR" : "en-US"
    const PERIODS = [
        { label: t.monitoring.periods.d7, days: 7 },
        { label: t.monitoring.periods.d30, days: 30 },
        { label: t.monitoring.periods.d90, days: 90 },
        { label: t.monitoring.periods.year, days: 365 },
    ]
    const [days, setDays] = useState(30)
    const [metrics, setMetrics] = useState<AiMetrics | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [mistralStatus, setMistralStatus] = useState<MistralStatus | null>(null)
    const [statusLoading, setStatusLoading] = useState(true)
    const [exportingPdf, setExportingPdf] = useState(false)

    const handleExportCsv = () => {
        if (!metrics) return
        downloadCsv(`monitoring-ia-smartticket-${new Date().toISOString().slice(0, 10)}.csv`, [
            {
                title: t.monitoring.csvLatencyTitle,
                headers: t.monitoring.csvLatencyHeaders,
                rows: metrics.latency_trend.map((entry) => [entry.name, entry.latence_ms, entry.appels]),
            },
            {
                title: t.monitoring.csvKbTitle,
                headers: t.monitoring.csvKbHeaders,
                rows: metrics.kb_events.map((e) => [e.date, e.chunks]),
            },
        ])
    }

    const handleExportPdf = async () => {
        setExportingPdf(true)
        try {
            const res = await fetch(`/api/analytics/ai-metrics/pdf?days=${days}`)
            if (!res.ok) return
            const blob = await res.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = `monitoring-ia-smartticket-${new Date().toISOString().slice(0, 10)}.pdf`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            URL.revokeObjectURL(url)
        } finally {
            setExportingPdf(false)
        }
    }

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
            .then(me => { if (me && !["admin", "sav", "superviseur"].includes(me.role)) router.replace("/dashboard") })
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
                        <h1 className="text-2xl font-bold tracking-tight">{t.monitoring.title}</h1>
                        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">Mistral AI</span>
                        {metrics?.model_name && (
                            <span className="text-xs font-mono bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded-full">
                                {metrics.model_name}
                            </span>
                        )}
                    </div>
                    <p className="text-muted-foreground">{t.monitoring.subtitle}</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex bg-muted/50 p-1 rounded-lg">
                        {PERIODS.map(({ label, days: d }) => (
                            <Button key={d} onClick={() => handlePeriodChange(d)}
                                variant={days === d ? "secondary" : "ghost"} size="sm"
                                className={`rounded-md ${days === d ? "shadow-sm bg-background text-foreground" : "hover:bg-background text-muted-foreground hover:text-foreground"}`}>
                                {label}
                            </Button>
                        ))}
                    </div>
                    <Button variant="outline" size="sm" onClick={handleExportCsv} disabled={isLoading}>
                        <Download className="h-4 w-4 mr-1.5" /> CSV
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleExportPdf} disabled={isLoading || exportingPdf}>
                        <FileText className="h-4 w-4 mr-1.5" /> {exportingPdf ? t.monitoring.exportingPdf : t.monitoring.exportPdf}
                    </Button>
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
                                        <span className="font-semibold">{alert.level === "critical" ? t.monitoring.critical : t.monitoring.warning} — </span>
                                        {alert.message}
                                        <span className="ml-2 text-xs opacity-70">
                                            {t.monitoring.thresholdSuffix(alert.threshold, alert.metric === "latency" ? "ms" : "%")}
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
                            <span>{t.monitoring.allNormal}</span>
                        </div>
                    )
                )}

                {/* KB Score */}
                {!isLoading && metrics && <KbScoreCard score={metrics.kb_score} totalCalls={metrics.total_calls} negativeRate={metrics.negative_rate} t={t} />}

                {/* Status Mistral */}
                <MistralStatusCard status={mistralStatus} loading={statusLoading} onRefresh={fetchMistralStatus} t={t} timeLocale={timeLocale} />

                {/* KPIs */}
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                    <KpiCard title={t.monitoring.totalCalls}
                        value={isLoading ? "…" : (metrics?.total_calls?.toLocaleString() ?? "0")}
                        trend={t.monitoring.overDays(days)} trendUp={true}
                        icon={<Activity className="h-4 w-4 text-indigo-500" />} />
                    <KpiCard title={t.monitoring.avgLatency}
                        value={isLoading ? "…" : fmtLatency(metrics?.avg_latency_ms ?? null)}
                        trend={metrics?.total_calls ? t.monitoring.overCalls(metrics.total_calls) : t.monitoring.noData}
                        trendUp={metrics?.avg_latency_ms == null || metrics.avg_latency_ms < 5000}
                        icon={<Clock className="h-4 w-4 text-blue-500" />}
                        prev={metrics?.prev_latency_ms ?? null}
                        curr={metrics?.avg_latency_ms ?? null}
                        vsPreviousLabel={t.monitoring.vsPrevious}
                        lowerIsBetter />
                    <KpiCard title={t.monitoring.errorRate}
                        value={isLoading ? "…" : `${metrics?.error_rate ?? 0}%`}
                        trend={metrics?.total_calls ? t.monitoring.callsAnalyzed(metrics.total_calls) : t.monitoring.noCalls}
                        trendUp={(metrics?.error_rate ?? 0) <= 5}
                        icon={<ShieldAlert className="h-4 w-4 text-red-400" />}
                        prev={metrics?.prev_error_rate ?? null}
                        curr={metrics?.error_rate ?? null}
                        vsPreviousLabel={t.monitoring.vsPrevious}
                        lowerIsBetter />
                    <KpiCard title={t.monitoring.noContext}
                        value={isLoading ? "…" : `${metrics?.no_context_rate ?? 0}%`}
                        trend={t.monitoring.noContextTrend}
                        trendUp={(metrics?.no_context_rate ?? 0) <= 30}
                        icon={<Database className="h-4 w-4 text-emerald-500" />}
                        prev={metrics?.prev_no_context_rate ?? null}
                        curr={metrics?.no_context_rate ?? null}
                        vsPreviousLabel={t.monitoring.vsPrevious}
                        lowerIsBetter />
                </div>

                {/* Recommandations + Historique */}
                {!isLoading && metrics && (
                    <div className="grid gap-6 lg:grid-cols-2">
                        <RecommendationsCard metrics={metrics} t={t} />
                        <ImprovementHistoryCard metrics={metrics} days={days} t={t} />
                    </div>
                )}

                {/* Graphique latence + carte sans contexte */}
                <div className="grid gap-6 lg:grid-cols-3">
                    <Card className="lg:col-span-2">
                        <CardHeader>
                            <CardTitle>{t.monitoring.latencyChartTitle}</CardTitle>
                            <CardDescription>
                                {t.monitoring.latencyChartDesc}
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {!metrics?.latency_trend?.length ? (
                                <div className="flex flex-col items-center justify-center h-[260px] text-muted-foreground text-sm gap-2">
                                    <Activity className="h-8 w-8 text-muted-foreground/40" />
                                    <span>{t.monitoring.noLatencyData}</span>
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
                                                formatter={(value: number | undefined) => [value != null ? `${value}ms` : "–", t.monitoring.latencyTooltipLabel]}
                                            />
                                            <Legend wrapperStyle={{ paddingTop: "12px" }} iconType="circle" />
                                            <Line type="monotone" dataKey="latence_ms" name={`${t.monitoring.latencyTooltipLabel} (ms)`} stroke="#4f46e5" strokeWidth={2} dot={{ r: 3, fill: "#4f46e5" }} activeDot={{ r: 5 }} />
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
                                <CardTitle className="text-sm font-medium text-muted-foreground">{t.monitoring.noContextCardTitle}</CardTitle>
                                <Database className="h-4 w-4 text-amber-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{isLoading ? "…" : `${metrics?.no_context_rate ?? 0}%`}</div>
                                <p className="text-xs text-muted-foreground mt-1">{t.monitoring.noContextOfRequests}</p>
                                {!isLoading && (metrics?.no_context_rate ?? 0) > 50 && (
                                    <p className="text-xs text-amber-600 mt-2 flex items-center gap-1">
                                        <AlertTriangle className="h-3 w-3" /> {t.monitoring.enrichKbSuggestion}
                                    </p>
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground">{t.monitoring.thresholdsTitle}</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2 text-xs text-muted-foreground">
                                <div className="flex justify-between"><span>{t.monitoring.thresholdLatencyWarning}</span><span className="font-mono">5 000ms</span></div>
                                <div className="flex justify-between"><span>{t.monitoring.thresholdLatencyCritical}</span><span className="font-mono">10 000ms</span></div>
                                <div className="flex justify-between"><span>{t.monitoring.thresholdErrorsWarning}</span><span className="font-mono">5%</span></div>
                                <div className="flex justify-between"><span>{t.monitoring.thresholdErrorsCritical}</span><span className="font-mono">15%</span></div>
                                <div className="flex justify-between"><span>{t.monitoring.thresholdNoContext}</span><span className="font-mono">70%</span></div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    )
}

type KbLevel = { label: string; message: string; color: string; bg: string; border: string; bar: string }

function getKbLevels(t: Messages): [number, KbLevel][] {
    return [
        [75, { label: t.monitoring.kbLevels.excellent.label, message: t.monitoring.kbLevels.excellent.message, color: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200", bar: "bg-emerald-500" }],
        [50, { label: t.monitoring.kbLevels.correct.label, message: t.monitoring.kbLevels.correct.message, color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", bar: "bg-amber-400" }],
        [25, { label: t.monitoring.kbLevels.insufficient.label, message: t.monitoring.kbLevels.insufficient.message, color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-200", bar: "bg-orange-500" }],
        [0, { label: t.monitoring.kbLevels.critical.label, message: t.monitoring.kbLevels.critical.message, color: "text-red-700", bg: "bg-red-50", border: "border-red-200", bar: "bg-red-500" }],
    ]
}

function getKbLevel(score: number, t: Messages): KbLevel {
    const levels = getKbLevels(t)
    for (const [threshold, level] of levels) {
        if (score >= threshold) return level
    }
    return levels[levels.length - 1][1]
}

function KbScoreInfo({ open, onToggle }: { open: boolean; onToggle: () => void }) {
    return (
        <button
            type="button"
            onClick={onToggle}
            className={`inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold cursor-pointer select-none transition-colors ${open ? "bg-slate-700 text-white" : "bg-muted text-muted-foreground hover:bg-muted-foreground/20"}`}
        >i</button>
    )
}

function KbScoreCard({ score, totalCalls, negativeRate, t }: { score: number | null; totalCalls: number; negativeRate: number; t: Messages }) {
    const [infoOpen, setInfoOpen] = useState(false)

    if (totalCalls < 5) {
        return (
            <Card className="border-border">
                <CardContent className="py-4 flex items-center gap-3 text-sm text-muted-foreground">
                    <Database className="h-4 w-4 flex-shrink-0" />
                    <span>{t.monitoring.kbUnavailablePrefix}<strong>{totalCalls}</strong>{t.monitoring.kbUnavailableSuffix}</span>
                </CardContent>
            </Card>
        )
    }

    const s = score ?? 0
    const level = getKbLevel(s, t)

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
                                    {t.monitoring.kbTitlePrefix} {level.label}
                                </span>
                                <span className={`text-xs font-bold ${level.color}`}>{s}/100</span>
                                <KbScoreInfo open={infoOpen} onToggle={() => setInfoOpen(o => !o)} />
                            </div>
                            <p className={`text-xs ${level.color} opacity-80`}>{level.message}</p>
                            {negativeRate > 0 && (
                                <p className="text-[10px] text-red-500 mt-0.5">{t.monitoring.negativeRate(negativeRate)}</p>
                            )}
                            {infoOpen && (
                                <div className="mt-3 p-3 bg-slate-900 text-white text-xs rounded-lg space-y-1.5">
                                    <p className="font-semibold mb-2">{t.monitoring.howCalculated}</p>
                                    <div className="flex justify-between gap-2 text-slate-300">
                                        <span>{t.monitoring.contextRetrieved}</span>
                                        <span className="font-bold text-white shrink-0">× 40%</span>
                                    </div>
                                    <div className="flex justify-between gap-2 text-slate-300">
                                        <span>{t.monitoring.userSatisfaction}</span>
                                        <span className="font-bold text-white shrink-0">× 40%</span>
                                    </div>
                                    <div className="flex justify-between gap-2 text-slate-300">
                                        <span>{t.monitoring.technicalReliability}</span>
                                        <span className="font-bold text-white shrink-0">× 20%</span>
                                    </div>
                                    <p className="mt-2 text-slate-400 text-[10px] pt-1 border-t border-slate-700">{t.monitoring.noFeedbackNote}</p>
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                        <div className="w-32">
                            <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                                <span>{t.monitoring.kbScoreLabel}</span><span>{s}%</span>
                            </div>
                            <div className="h-2 w-full rounded-full bg-white/60 border border-white/40 overflow-hidden">
                                <div className={`h-full rounded-full transition-all duration-500 ${level.bar}`} style={{ width: `${s}%` }} />
                            </div>
                        </div>
                        {s < 75 && (
                            <a href="/knowledge-base"
                                className={`text-xs font-semibold px-3 py-1.5 rounded-lg border ${level.border} ${level.color} bg-white/70 hover:bg-white transition-colors whitespace-nowrap`}>
                                {t.monitoring.enrichKb}
                            </a>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

function getStatusConfig(t: Messages) {
    return {
        operational: { label: t.monitoring.statusLabels.operational, dot: "bg-emerald-500", badge: "bg-emerald-50 text-emerald-700 border-emerald-200" },
        degraded: { label: t.monitoring.statusLabels.degraded, dot: "bg-amber-500", badge: "bg-amber-50 text-amber-700 border-amber-200" },
        outage: { label: t.monitoring.statusLabels.outage, dot: "bg-red-500", badge: "bg-red-50 text-red-700 border-red-200" },
        unknown: { label: t.monitoring.statusLabels.unknown, dot: "bg-slate-400", badge: "bg-slate-50 text-slate-600 border-slate-200" },
    }
}

function MistralStatusCard({ status, loading, onRefresh, t, timeLocale }: { status: MistralStatus | null; loading: boolean; onRefresh: () => void; t: Messages; timeLocale: string }) {
    const overall = status?.overall ?? "unknown"
    const cfg = getStatusConfig(t)[overall]

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 rounded-full ${cfg.dot} ${overall === "operational" ? "animate-pulse" : ""}`} />
                        <CardTitle className="text-base">{t.monitoring.mistralStatusTitle}</CardTitle>
                        <a href="https://status.mistral.ai" target="_blank" rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-foreground transition-colors">
                            <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                    </div>
                    <div className="flex items-center gap-2">
                        {status?.fetched_at && (
                            <span className="text-xs text-muted-foreground">
                                {new Date(status.fetched_at).toLocaleTimeString(timeLocale, { hour: "2-digit", minute: "2-digit" })}
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
                        {loading ? t.monitoring.loadingStatus : cfg.label}
                    </span>
                    <CardDescription className="text-xs">{t.monitoring.updatedEvery60s}</CardDescription>
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
                            const s = getStatusConfig(t)[c.status]
                            return (
                                <div key={c.name} className="flex items-center gap-2 rounded-lg border px-3 py-2 bg-muted/50">
                                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${s.dot}`} />
                                    <div className="min-w-0">
                                        <p className="text-xs font-medium truncate">{c.name}</p>
                                        {c.uptime && (
                                            <p className="text-[10px] text-muted-foreground">{c.uptime} {t.monitoring.uptimeSuffix}</p>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                ) : (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                        <AlertTriangle className="h-4 w-4" />
                        <span>{t.monitoring.statusUnavailable} <a href="https://status.mistral.ai" target="_blank" rel="noopener noreferrer" className="underline">{t.monitoring.seeDirectly}</a></span>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

type Reco = { icon: React.ReactNode; title: string; detail: string; action?: { label: string; href: string } }

function buildRecommendations(m: AiMetrics, t: Messages): Reco[] {
    const recos: Reco[] = []

    if (m.no_context_rate > 30) {
        recos.push({
            icon: <BookOpen className="h-4 w-4 text-amber-500" />,
            title: t.monitoring.recoEnrichKbTitle,
            detail: t.monitoring.recoEnrichKbDetail(m.no_context_rate),
            action: { label: t.monitoring.recoManageKb, href: "/knowledge-base" },
        })
    }

    if (m.avg_latency_ms !== null && m.avg_latency_ms > 5000) {
        recos.push({
            icon: <Zap className="h-4 w-4 text-yellow-500" />,
            title: t.monitoring.recoHighLatencyTitle,
            detail: t.monitoring.recoHighLatencyDetail(m.avg_latency_ms),
        })
    }

    if (m.error_rate > 5) {
        recos.push({
            icon: <Wrench className="h-4 w-4 text-red-500" />,
            title: t.monitoring.recoCheckApiTitle,
            detail: t.monitoring.recoCheckApiDetail(m.error_rate),
        })
    }

    if (m.avg_rag_chunks < 1 && m.total_calls > 0) {
        recos.push({
            icon: <Database className="h-4 w-4 text-muted-foreground" />,
            title: t.monitoring.recoNoChunksTitle,
            detail: t.monitoring.recoNoChunksDetail,
            action: { label: t.monitoring.recoManageKb, href: "/knowledge-base" },
        })
    }

    if (recos.length === 0) {
        recos.push({
            icon: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
            title: t.monitoring.recoHealthyTitle,
            detail: t.monitoring.recoHealthyDetail,
        })
    }

    return recos
}

function RecommendationsCard({ metrics, t }: { metrics: AiMetrics; t: Messages }) {
    const recos = buildRecommendations(metrics, t)
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-yellow-500" />
                    <CardTitle className="text-base">{t.monitoring.recommendationsTitle}</CardTitle>
                </div>
                <CardDescription>{t.monitoring.recommendationsSubtitle}</CardDescription>
            </CardHeader>
            <CardContent>
                <div className="space-y-3">
                    {recos.map((r, i) => (
                        <div key={i} className="flex items-start gap-3 rounded-lg border px-4 py-3 bg-muted/50">
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

function DeltaBadge({ curr, prev, lowerIsBetter, vsPreviousLabel }: { curr: number | null; prev: number | null; lowerIsBetter?: boolean; vsPreviousLabel: string }) {
    if (curr === null || prev === null || prev === 0) return null
    const pct = Math.round(((curr - prev) / prev) * 100)
    if (pct === 0) return null
    const improved = lowerIsBetter ? pct < 0 : pct > 0
    return (
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ml-2 ${improved ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
            {pct > 0 ? "+" : ""}{pct}% {vsPreviousLabel}
        </span>
    )
}

function KpiCard({ title, value, trend, trendUp, icon, curr, prev, lowerIsBetter, vsPreviousLabel }: {
    title: string; value: string; trend: string; trendUp: boolean; icon: React.ReactNode
    curr?: number | null; prev?: number | null; lowerIsBetter?: boolean; vsPreviousLabel?: string
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
                    {vsPreviousLabel && <DeltaBadge curr={curr ?? null} prev={prev ?? null} lowerIsBetter={lowerIsBetter} vsPreviousLabel={vsPreviousLabel} />}
                </div>
                <p className="text-xs text-muted-foreground flex items-center mt-1">
                    {trendUp ? <TrendingUp className="h-3 w-3 text-green-500 mr-1" /> : <TrendingDown className="h-3 w-3 text-red-500 mr-1" />}
                    <span className="ml-1">{trend}</span>
                </p>
            </CardContent>
        </Card>
    )
}

function ImprovementHistoryCard({ metrics, days, t }: { metrics: AiMetrics; days: number; t: Messages }) {
    const hasKbEvents = metrics.kb_events?.length > 0
    const hasPrev = metrics.prev_latency_ms !== null || metrics.prev_error_rate !== null || metrics.prev_no_context_rate !== null

    const deltas: { label: string; prev: number | null; curr: number | null; unit: string; lowerIsBetter: boolean }[] = [
        { label: t.monitoring.deltaLabels.latency, prev: metrics.prev_latency_ms, curr: metrics.avg_latency_ms, unit: "ms", lowerIsBetter: true },
        { label: t.monitoring.deltaLabels.errorRate, prev: metrics.prev_error_rate, curr: metrics.error_rate, unit: "%", lowerIsBetter: true },
        { label: t.monitoring.deltaLabels.noContext, prev: metrics.prev_no_context_rate, curr: metrics.no_context_rate, unit: "%", lowerIsBetter: true },
    ]

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-indigo-500" />
                    <CardTitle className="text-base">{t.monitoring.historyTitle}</CardTitle>
                </div>
                <CardDescription>{t.monitoring.historySubtitle}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* KB events timeline */}
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">{t.monitoring.kbEventsOverDays(days)}</p>
                    {hasKbEvents ? (
                        <div className="space-y-1.5">
                            {metrics.kb_events.map((e, i) => (
                                <div key={i} className="flex items-center gap-2 text-sm">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
                                    <span className="font-mono text-xs text-muted-foreground w-12">{e.date}</span>
                                    <span className="text-xs">{t.monitoring.chunksAdded(e.chunks)}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground italic">{t.monitoring.noEnrichments}</p>
                    )}
                </div>

                {/* Period comparison */}
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">{t.monitoring.impactMeasured(days)}</p>
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
                        <p className="text-xs text-muted-foreground italic">{t.monitoring.notEnoughData}</p>
                    )}
                </div>
            </CardContent>
        </Card>
    )
}
