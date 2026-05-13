"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
    BarChart,
    Bar,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell
} from 'recharts';
import {
    TrendingUp,
    TrendingDown,
    MessageSquare,
    Zap,
    Clock,
    Star,
    AlertTriangle,
    AlertCircle,
    CheckCircle2,
    Activity,
    ShieldAlert,
    Database,
} from "lucide-react"


type DayEntry = { name: string; IA: number; Humain: number }
type AgentEntry = { name: string; initials: string; conversations: number }

type ReasonEntry = { name: string; value: number; color: string }

type AlertEntry = {
    level: "warning" | "critical"
    metric: string
    message: string
    value: number
    threshold: number
}

type AnalyticsData = {
    total_sessions: number
    ai_resolution_rate: number
    transferred_count: number
    satisfaction_score: number | null
    daily_messages: DayEntry[]
    sav_agents: AgentEntry[]
    transfer_reasons: ReasonEntry[]
    alerts: AlertEntry[]
}

type LatencyEntry = { name: string; latence_ms: number; appels: number }

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

export default function AnalyticsPage() {
    const [days, setDays] = useState(30)
    const [data, setData] = useState<AnalyticsData | null>(null)
    const [aiMetrics, setAiMetrics] = useState<AiMetrics | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        setIsLoading(true)
        Promise.all([
            fetch(`/api/analytics/stats?days=${days}`).then(r => r.ok ? r.json() : null),
            fetch(`/api/analytics/ai-metrics?days=${days}`).then(r => r.ok ? r.json() : null),
        ])
            .then(([stats, metrics]) => {
                if (stats) setData(stats)
                if (metrics) setAiMetrics(metrics)
            })
            .catch(() => null)
            .finally(() => setIsLoading(false))
    }, [days])

    const chartData: DayEntry[] = data?.daily_messages?.length
        ? data.daily_messages
        : [{ name: "–", IA: 0, Humain: 0 }]

    const satisfactionDisplay = data?.satisfaction_score != null
        ? data.satisfaction_score.toFixed(2)
        : "–"

    return (
        <div className="flex flex-col min-h-full">
            {/* Header & Controls */}
            <div className="p-8 pb-4 bg-background border-b flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Analytique IA</h1>
                    <p className="text-muted-foreground">Performance de l&apos;assistant virtuel et métriques clés</p>
                </div>

                <div className="flex bg-muted/50 p-1 rounded-lg">
                    {PERIODS.map(({ label, days: d }) => (
                        <Button
                            key={d}
                            onClick={() => {
                                setIsLoading(true)
                                setDays(d)
                            }}
                            variant={days === d ? "secondary" : "ghost"}
                            size="sm"
                            className={`rounded-md ${days === d ? "shadow-sm bg-background text-foreground" : "hover:bg-background text-muted-foreground hover:text-foreground"}`}
                        >
                            {label}
                        </Button>
                    ))}
                </div>
            </div>

            <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">

                {/* Alert Banner */}
                {!isLoading && (() => {
                    const allAlerts = [...(data?.alerts ?? []), ...(aiMetrics?.alerts ?? [])]
                    return allAlerts.length > 0 ? (
                        <div className="space-y-2">
                            {allAlerts.map((alert, i) => (
                                <div
                                    key={i}
                                    className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${
                                        alert.level === "critical"
                                            ? "bg-red-50 border-red-200 text-red-800"
                                            : "bg-amber-50 border-amber-200 text-amber-800"
                                    }`}
                                    role="alert"
                                >
                                    {alert.level === "critical"
                                        ? <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                        : <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                    }
                                    <div className="flex-1">
                                        <span className="font-semibold capitalize">{alert.level === "critical" ? "Critique" : "Attention"} — </span>
                                        {alert.message}
                                        <span className="ml-2 text-xs opacity-70">
                                            (seuil : {alert.threshold}{["ai_resolution_rate", "transfer_rate", "error_rate", "rag_quality"].includes(alert.metric) ? "%" : alert.metric === "latency" ? "ms" : "/5"})
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                            <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                            <span>Toutes les métriques IA sont dans les seuils normaux.</span>
                        </div>
                    )
                })()}

                {/* KPI Metrics Grid */}
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                    <KpiCard
                        title="Conversations Totales"
                        value={isLoading ? "…" : (data?.total_sessions?.toLocaleString() ?? "0")}
                        trend="ce mois"
                        trendUp={true}
                        icon={<MessageSquare className="h-4 w-4 text-muted-foreground" />}
                    />
                    <KpiCard
                        title="Taux de résolution IA"
                        value={isLoading ? "…" : `${data?.ai_resolution_rate ?? 0}%`}
                        trend="ce mois"
                        trendUp={true}
                        icon={<Zap className="h-4 w-4 text-yellow-500" />}
                    />
                    <KpiCard
                        title="Latence IA moyenne"
                        value={isLoading ? "…" : fmtLatency(aiMetrics?.avg_latency_ms ?? null)}
                        trend={aiMetrics?.total_calls ? `sur ${aiMetrics.total_calls} appels` : "aucune donnée"}
                        trendUp={aiMetrics?.avg_latency_ms == null || aiMetrics.avg_latency_ms < 5000}
                        icon={<Clock className="h-4 w-4 text-blue-500" />}
                    />
                    <KpiCard
                        title="Score de Satisfaction"
                        value={isLoading ? "…" : satisfactionDisplay}
                        trend={data?.satisfaction_score != null ? "basé sur les retours" : "aucun retour"}
                        trendUp={data?.satisfaction_score != null ? data.satisfaction_score >= 2.5 : true}
                        icon={<Star className="h-4 w-4 text-purple-500" />}
                    />
                </div>

                {/* Data Visualization Grid */}
                <div className="grid gap-6 lg:grid-cols-3">

                    {/* Bar Chart: Conversation Evolution */}
                    <Card className="lg:col-span-2">
                        <CardHeader>
                            <CardTitle>Évolution des Conversations</CardTitle>
                            <CardDescription>
                                Comparaison du volume traité par IA vs Humain sur les {days} derniers jours.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="h-[300px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart
                                        data={chartData}
                                        margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                                    >
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                        <XAxis
                                            dataKey="name"
                                            stroke="#64748B"
                                            fontSize={12}
                                            tickLine={false}
                                            axisLine={false}
                                        />
                                        <YAxis
                                            stroke="#64748B"
                                            fontSize={12}
                                            tickLine={false}
                                            axisLine={false}
                                        />
                                        <Tooltip
                                            cursor={{ fill: '#F1F5F9' }}
                                            contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                        />
                                        <Legend wrapperStyle={{ paddingTop: '20px' }} iconType="circle" />
                                        <Bar dataKey="IA" fill="#4f46e5" radius={[4, 4, 0, 0]} barSize={30} />
                                        <Bar dataKey="Humain" fill="#cbd5e1" radius={[4, 4, 0, 0]} barSize={30} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Donut Chart: Transfer Reasons (dynamic) */}
                    <Card className="lg:col-span-1">
                        <CardHeader>
                            <CardTitle>Raisons du Transfert</CardTitle>
                            <CardDescription>Pourquoi l&apos;IA passe le relais.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {!data?.transfer_reasons?.length ? (
                                <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground text-sm gap-2">
                                    <span>Aucun transfert sur cette période</span>
                                </div>
                            ) : (() => {
                                const reasons = data.transfer_reasons
                                const total = reasons.reduce((a, b) => a + b.value, 0)
                                return (
                                    <>
                                        <div className="h-[200px] w-full relative">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <PieChart>
                                                    <Pie
                                                        data={reasons}
                                                        cx="50%"
                                                        cy="50%"
                                                        innerRadius={60}
                                                        outerRadius={80}
                                                        paddingAngle={5}
                                                        dataKey="value"
                                                    >
                                                        {reasons.map((entry, index) => (
                                                            <Cell key={`cell-${index}`} fill={entry.color} strokeWidth={0} />
                                                        ))}
                                                    </Pie>
                                                    <Tooltip />
                                                </PieChart>
                                            </ResponsiveContainer>
                                            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                                <span className="text-3xl font-bold">{total}</span>
                                                <span className="text-xs text-muted-foreground">Total</span>
                                            </div>
                                        </div>
                                        <div className="mt-4 space-y-2">
                                            {reasons.map((item, index) => (
                                                <div key={index} className="flex justify-between items-center text-sm">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }}></div>
                                                        <span className="text-muted-foreground">{item.name}</span>
                                                    </div>
                                                    <span className="font-semibold">{total > 0 ? Math.round((item.value / total) * 100) : 0}%</span>
                                                </div>
                                            ))}
                                        </div>
                                    </>
                                )
                            })()}
                        </CardContent>
                    </Card>
                </div>

                {/* AI Monitoring — C11 */}
                <div>
                    <div className="flex items-center gap-2 mb-4">
                        <Activity className="h-5 w-5 text-indigo-500" />
                        <h2 className="text-lg font-semibold tracking-tight">Monitoring du modèle IA</h2>
                        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">Mistral AI · {days}j</span>
                    </div>
                    <div className="grid gap-6 lg:grid-cols-3">
                        <div className="space-y-4">
                            <div className="grid grid-cols-1 gap-4">
                                <KpiCard
                                    title="Taux d'erreur IA"
                                    value={isLoading ? "…" : `${aiMetrics?.error_rate ?? 0}%`}
                                    trend={aiMetrics?.total_calls ? `${aiMetrics.total_calls} appels analysés` : "aucun appel"}
                                    trendUp={(aiMetrics?.error_rate ?? 0) <= 5}
                                    icon={<ShieldAlert className="h-4 w-4 text-red-400" />}
                                />
                                <KpiCard
                                    title="Chunks RAG moyens"
                                    value={isLoading ? "…" : `${aiMetrics?.avg_rag_chunks ?? 0}`}
                                    trend="extraits KB par requête"
                                    trendUp={(aiMetrics?.avg_rag_chunks ?? 0) > 0}
                                    icon={<Database className="h-4 w-4 text-emerald-500" />}
                                />
                                <KpiCard
                                    title="Requêtes sans contexte"
                                    value={isLoading ? "…" : `${aiMetrics?.no_context_rate ?? 0}%`}
                                    trend="base de connaissances vide"
                                    trendUp={(aiMetrics?.no_context_rate ?? 0) < 50}
                                    icon={<Database className="h-4 w-4 text-amber-400" />}
                                />
                            </div>
                        </div>
                        <Card className="lg:col-span-2">
                            <CardHeader>
                                <CardTitle>Évolution de la latence Mistral</CardTitle>
                                <CardDescription>Temps moyen de génération par jour (ms) — du premier token au dernier.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {!aiMetrics?.latency_trend?.length ? (
                                    <div className="flex flex-col items-center justify-center h-[260px] text-muted-foreground text-sm gap-2">
                                        <Activity className="h-8 w-8 text-slate-200" />
                                        <span>Aucune donnée — les métriques s&apos;accumulent au fil des échanges</span>
                                    </div>
                                ) : (
                                    <div className="h-[260px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={aiMetrics.latency_trend} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                                <XAxis dataKey="name" stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} />
                                                <YAxis stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}ms`} />
                                                <Tooltip
                                                    contentStyle={{ backgroundColor: "#fff", borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                                                    formatter={(value: number) => [`${value}ms`, "Latence"]}
                                                />
                                                <Legend wrapperStyle={{ paddingTop: "12px" }} iconType="circle" />
                                                <Line type="monotone" dataKey="latence_ms" name="Latence (ms)" stroke="#4f46e5" strokeWidth={2} dot={{ r: 3, fill: "#4f46e5" }} activeDot={{ r: 5 }} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>

                {/* Agent Performance Table */}
                <Card>
                    <CardHeader>
                        <CardTitle>Performance des Agents (Support Humain)</CardTitle>
                        <CardDescription>Métriques détaillées pour les agents prenant le relais de l&apos;IA.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {/* Header Row */}
                            <div className="grid grid-cols-12 gap-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider pb-2 border-b">
                                <div className="col-span-4 pl-2">Agent</div>
                                <div className="col-span-2 text-center">Conversations</div>
                                <div className="col-span-2 text-center">Satisfaction</div>
                                <div className="col-span-2 text-center">Temps Moy.</div>
                                <div className="col-span-2 text-right pr-2">Performance</div>
                            </div>

                            {/* Rows */}
                            {isLoading ? (
                                <div className="text-sm text-muted-foreground py-4 text-center">Chargement…</div>
                            ) : data?.sav_agents?.length ? (
                                data.sav_agents.map((agent, index) => (
                                    <div key={index} className="grid grid-cols-12 gap-4 items-center py-2 hover:bg-muted/50 rounded-lg transition-colors">
                                        <div className="col-span-4 flex items-center gap-3 pl-2">
                                            <Avatar className="h-8 w-8">
                                                <AvatarFallback>{agent.initials}</AvatarFallback>
                                            </Avatar>
                                            <span className="font-medium text-sm">{agent.name}</span>
                                        </div>
                                        <div className="col-span-2 text-center text-sm">{agent.conversations}</div>
                                        <div className="col-span-2 flex items-center justify-center gap-1 text-sm text-muted-foreground">–</div>
                                        <div className="col-span-2 text-center text-sm text-muted-foreground">–</div>
                                        <div className="col-span-2 pr-2 text-right text-sm text-muted-foreground">–</div>
                                    </div>
                                ))
                            ) : (
                                <div className="text-sm text-muted-foreground py-4 text-center">Aucun agent SAV trouvé.</div>
                            )}
                        </div>
                    </CardContent>
                </Card>

            </div>
        </div>
    )
}

function KpiCard({ title, value, trend, trendUp, icon }: { title: string, value: string, trend: string, trendUp: boolean, icon: React.ReactNode }) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
                {icon}
            </CardHeader>
            <CardContent>
                <div className="text-2xl font-bold">{value}</div>
                <p className="text-xs text-muted-foreground flex items-center mt-1">
                    {trendUp ? (
                        <TrendingUp className="h-3 w-3 text-green-500 mr-1" />
                    ) : (
                        <TrendingDown className="h-3 w-3 text-red-500 mr-1" />
                    )}
                    <span className="ml-1">{trend}</span>
                </p>
            </CardContent>
        </Card>
    )
}
