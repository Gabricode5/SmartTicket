"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    PieChart, Pie, Cell,
} from "recharts"
import {
    TrendingUp, TrendingDown, MessageSquare, Zap, Star,
    AlertTriangle, AlertCircle, CheckCircle2, Download, FileText,
} from "lucide-react"
import { downloadCsv } from "@/lib/csv"

type DayEntry = { name: string; IA: number; Humain: number }
type AgentEntry = { name: string; initials: string; conversations: number }
type ReasonEntry = { name: string; value: number; color: string }
type AlertEntry = { level: "warning" | "critical"; metric: string; message: string; recommendation?: string; value: number; threshold: number }

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

const PERIODS = [
    { label: "7 Jours", days: 7 },
    { label: "30 Jours", days: 30 },
    { label: "90 Jours", days: 90 },
    { label: "Année", days: 365 },
]

export default function AnalyticsPage() {
    const router = useRouter()
    const [days, setDays] = useState(30)
    const [data, setData] = useState<AnalyticsData | null>(null)
    const [exportingPdf, setExportingPdf] = useState(false)

    const isLoading = data === null

    const handlePeriodChange = (d: number) => {
        if (d === days) return
        setData(null)
        setDays(d)
    }

    const handleExportCsv = () => {
        if (!data) return
        downloadCsv(`analytics-smartticket-${new Date().toISOString().slice(0, 10)}.csv`, [
            {
                title: "Évolution quotidienne des conversations",
                headers: ["Jour", "Messages IA", "Messages humains"],
                rows: data.daily_messages.map((d) => [d.name, d.IA, d.Humain]),
            },
            {
                title: "Raisons de transfert",
                headers: ["Raison", "Nombre"],
                rows: data.transfer_reasons.map((r) => [r.name, r.value]),
            },
            {
                title: "Agents SAV",
                headers: ["Agent", "Conversations traitées"],
                rows: data.sav_agents.map((a) => [a.name, a.conversations]),
            },
        ])
    }

    const handleExportPdf = async () => {
        setExportingPdf(true)
        try {
            const res = await fetch(`/api/analytics/stats/pdf?days=${days}`)
            if (!res.ok) return
            const blob = await res.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = `analytics-smartticket-${new Date().toISOString().slice(0, 10)}.pdf`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            URL.revokeObjectURL(url)
        } finally {
            setExportingPdf(false)
        }
    }

    useEffect(() => {
        fetch("/api/me")
            .then(r => { if (r.status === 401) { router.replace("/login"); return null } return r.ok ? r.json() : null })
            .then(me => { if (me && !["admin", "sav", "superviseur"].includes(me.role)) router.replace("/dashboard") })
            .catch(() => {})
    }, [router])

    useEffect(() => {
        fetch(`/api/analytics/stats?days=${days}`)
            .then(r => r.ok ? r.json() : null)
            .then(stats => setData(stats ?? null))
            .catch(() => setData(null))
    }, [days])

    const chartData: DayEntry[] = data?.daily_messages?.length ? data.daily_messages : [{ name: "–", IA: 0, Humain: 0 }]

    return (
        <div className="flex flex-col min-h-full">
            {/* Header */}
            <div className="p-8 pb-4 bg-background border-b flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Analytique Application</h1>
                    <p className="text-muted-foreground">Sessions, satisfaction et performance du service SAV.</p>
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
                        <FileText className="h-4 w-4 mr-1.5" /> {exportingPdf ? "…" : "PDF"}
                    </Button>
                </div>
            </div>

            <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">

                {/* Alertes */}
                {!isLoading && (() => {
                    const alerts = data?.alerts ?? []
                    return alerts.length > 0 ? (
                        <div className="space-y-2">
                            {alerts.map((alert, i) => (
                                <div key={i} role="alert"
                                    className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${alert.level === "critical" ? "bg-red-50 border-red-200 text-red-800" : "bg-amber-50 border-amber-200 text-amber-800"}`}>
                                    {alert.level === "critical" ? <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" /> : <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />}
                                    <div className="flex-1">
                                        <span className="font-semibold">{alert.level === "critical" ? "Critique" : "Attention"} — </span>
                                        {alert.message}
                                        <span className="ml-2 text-xs opacity-70">(seuil : {alert.threshold}{alert.metric.includes("rate") ? "%" : "/5"})</span>
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
                            <span>Toutes les métriques applicatives sont dans les seuils normaux.</span>
                        </div>
                    )
                })()}

                {/* KPIs */}
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    <KpiCard title="Conversations totales"
                        value={isLoading ? "…" : (data?.total_sessions?.toLocaleString() ?? "0")}
                        trend={`sur ${days} jours`} trendUp={true}
                        icon={<MessageSquare className="h-4 w-4 text-muted-foreground" />} />
                    <KpiCard title="Taux de résolution IA"
                        value={isLoading ? "…" : `${data?.ai_resolution_rate ?? 0}%`}
                        trend="sessions résolues par l'IA" trendUp={(data?.ai_resolution_rate ?? 0) >= 70}
                        icon={<Zap className="h-4 w-4 text-yellow-500" />} />
                    <KpiCard title="Score de satisfaction"
                        value={isLoading ? "…" : (data?.satisfaction_score != null ? data.satisfaction_score.toFixed(2) : "–")}
                        trend={data?.satisfaction_score != null ? "basé sur les pouces rouges 👎" : "aucune réponse négative"}
                        trendUp={data?.satisfaction_score != null ? data.satisfaction_score >= 2.5 : true}
                        icon={<Star className="h-4 w-4 text-purple-500" />} />
                </div>

                {/* Graphiques */}
                <div className="grid gap-6 lg:grid-cols-3">
                    <Card className="lg:col-span-2">
                        <CardHeader>
                            <CardTitle>Évolution des conversations</CardTitle>
                            <CardDescription>Volume traité par l&apos;IA vs agents humains sur les {days} derniers jours.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="h-[300px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                        <XAxis dataKey="name" stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} />
                                        <YAxis stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} />
                                        <Tooltip cursor={{ fill: "#F1F5F9" }} contentStyle={{ backgroundColor: "#fff", borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }} />
                                        <Legend wrapperStyle={{ paddingTop: "20px" }} iconType="circle" />
                                        <Bar dataKey="IA" fill="#4f46e5" radius={[4, 4, 0, 0]} barSize={30} />
                                        <Bar dataKey="Humain" fill="#cbd5e1" radius={[4, 4, 0, 0]} barSize={30} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Raisons de transfert</CardTitle>
                            <CardDescription>Pourquoi l&apos;IA passe le relais à un agent SAV.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {!data?.transfer_reasons?.length ? (
                                <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground text-sm">Aucun transfert sur cette période</div>
                            ) : (() => {
                                const reasons = data.transfer_reasons
                                const total = reasons.reduce((a, b) => a + b.value, 0)
                                return (
                                    <>
                                        <div className="h-[200px] w-full relative">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <PieChart>
                                                    <Pie data={reasons} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                                                        {reasons.map((entry, i) => <Cell key={i} fill={entry.color} strokeWidth={0} />)}
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
                                            {reasons.map((item, i) => (
                                                <div key={i} className="flex justify-between items-center text-sm">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
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

                {/* Agents SAV */}
                <Card>
                    <CardHeader>
                        <CardTitle>Performance des agents SAV</CardTitle>
                        <CardDescription>Métriques des agents prenant le relais de l&apos;IA.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            <div className="grid grid-cols-12 gap-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider pb-2 border-b">
                                <div className="col-span-5 pl-2">Agent</div>
                                <div className="col-span-3 text-center">Conversations</div>
                                <div className="col-span-4 text-right pr-2">Statut</div>
                            </div>
                            {isLoading ? (
                                <div className="text-sm text-muted-foreground py-4 text-center">Chargement…</div>
                            ) : data?.sav_agents?.length ? (
                                data.sav_agents.map((agent, i) => (
                                    <div key={i} className="grid grid-cols-12 gap-4 items-center py-2 hover:bg-muted/50 rounded-lg transition-colors">
                                        <div className="col-span-5 flex items-center gap-3 pl-2">
                                            <Avatar className="h-8 w-8"><AvatarFallback>{agent.initials}</AvatarFallback></Avatar>
                                            <span className="font-medium text-sm">{agent.name}</span>
                                        </div>
                                        <div className="col-span-3 text-center text-sm">{agent.conversations}</div>
                                        <div className="col-span-4 text-right pr-2">
                                            <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full">Actif</span>
                                        </div>
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
