"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Sparkles, Send, UserPlus } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useLocale } from "@/lib/i18n/LocaleContext"
import type { Ticket } from "@/components/dashboard/types"
import { REASON_STYLES } from "@/components/dashboard/types"

type TicketMessage = { id: number; role: "user" | "ai" | "sav"; content: string; createdAt: string }
type Agent = { id: number; username: string }

const STATUS_STYLES: Record<string, string> = {
    new: "bg-sky-100 text-sky-700 border-sky-200",
    in_progress: "bg-amber-100 text-amber-700 border-amber-200",
    resolved: "bg-emerald-100 text-emerald-700 border-emerald-200",
    closed: "bg-slate-100 text-slate-600 border-slate-200",
}

export default function TicketDetailPage() {
    const params = useParams()
    const router = useRouter()
    const ticketIdParam = Array.isArray(params.id) ? params.id[0] : params.id

    const { user, isLoading: isLoadingUser } = useCurrentUser()
    const { messages: t, locale } = useLocale()
    const dateLocale = locale === "fr" ? "fr-FR" : "en-US"
    const reasonLabel = (reason: string | null | undefined) => (reason ? t.common.reasons[reason as keyof typeof t.common.reasons] ?? reason : reason)

    const [ticket, setTicket] = useState<Ticket | null>(null)
    const [messages, setMessages] = useState<TicketMessage[]>([])
    const [agents, setAgents] = useState<Agent[]>([])
    const [reply, setReply] = useState("")
    const [isLoading, setIsLoading] = useState(true)
    const [notFound, setNotFound] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [subscriptionSuspended, setSubscriptionSuspended] = useState(false)
    const [isTaking, setIsTaking] = useState(false)
    const [isSending, setIsSending] = useState(false)
    const [assignTarget, setAssignTarget] = useState<string>("")

    const canManageTeam = user?.role === "admin" || user?.role === "superviseur"

    useEffect(() => {
        if (!isLoadingUser && user && user.role === "user") router.replace("/dashboard")
    }, [isLoadingUser, user, router])

    const loadTicket = async () => {
        setIsLoading(true)
        setError(null)
        setSubscriptionSuspended(false)
        try {
            const ticketRes = await fetch(`/api/tickets/${ticketIdParam}`)
            if (ticketRes.status === 401) { setError(t.tickets.sessionExpired); return }
            if (ticketRes.status === 402) { setSubscriptionSuspended(true); return }
            if (ticketRes.status === 404) { setNotFound(true); return }
            if (!ticketRes.ok) { setError(t.tickets.loadError); return }
            const ticketData: Ticket = await ticketRes.json()
            setTicket(ticketData)

            const messagesRes = await fetch(`/api/messages?session_id=${ticketData.session_id}`)
            if (messagesRes.ok) {
                const rawMessages = await messagesRes.json()
                if (Array.isArray(rawMessages)) {
                    setMessages(rawMessages.map((m: { id: number; type_envoyeur: string; contenu?: string | null; date_creation?: string | null }) => ({
                        id: m.id,
                        role: m.type_envoyeur === "sav" ? "sav" : m.type_envoyeur === "ai" ? "ai" : "user",
                        content: m.contenu ?? "",
                        createdAt: m.date_creation
                            ? new Date(m.date_creation).toLocaleTimeString(dateLocale, { hour: "2-digit", minute: "2-digit" })
                            : "",
                    })))
                }
            }
        } catch {
            setError(t.tickets.loadError)
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        if (!user || user.role === "user" || !ticketIdParam) return
        loadTicket()
        // eslint-disable-next-line react-hooks/exhaustive-deps -- rechargement piloté par ticketIdParam/user, pas par la langue
    }, [user, ticketIdParam])

    useEffect(() => {
        if (!canManageTeam) return
        fetch("/api/users?role=sav")
            .then((res) => (res.ok ? res.json() : []))
            .then((data) => setAgents(Array.isArray(data) ? data : []))
            .catch(() => {})
    }, [canManageTeam])

    const handleTake = async () => {
        if (!ticket || isTaking) return
        setIsTaking(true)
        try {
            const res = await fetch(`/api/tickets/${ticket.id}/assign`, {
                method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
            })
            if (res.ok) setTicket(await res.json())
            else setError(t.tickets.actionError)
        } catch {
            setError(t.tickets.actionError)
        } finally {
            setIsTaking(false)
        }
    }

    const handleAssign = async () => {
        if (!ticket || !assignTarget) return
        try {
            const res = await fetch(`/api/tickets/${ticket.id}/assign`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ agent_id: Number(assignTarget) }),
            })
            if (res.ok) setTicket(await res.json())
            else setError(t.tickets.actionError)
        } catch {
            setError(t.tickets.actionError)
        }
    }

    const handleStatusChange = async (status: string) => {
        if (!ticket) return
        try {
            const res = await fetch(`/api/tickets/${ticket.id}/status`, {
                method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
            })
            if (res.ok) setTicket(await res.json())
            else setError(t.tickets.actionError)
        } catch {
            setError(t.tickets.actionError)
        }
    }

    const handleWaitingOnToggle = async () => {
        if (!ticket) return
        const next = ticket.waiting_on === "us" ? "customer" : "us"
        try {
            const res = await fetch(`/api/tickets/${ticket.id}/waiting_on`, {
                method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ waiting_on: next }),
            })
            if (res.ok) setTicket(await res.json())
            else setError(t.tickets.actionError)
        } catch {
            setError(t.tickets.actionError)
        }
    }

    const handleSendReply = async () => {
        const trimmed = reply.trim()
        if (!trimmed || !ticket || isSending) return
        setIsSending(true)
        try {
            const res = await fetch("/api/messages", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id_session: ticket.session_id, type_envoyeur: "sav", contenu: trimmed }),
            })
            if (!res.ok) { setError(t.tickets.actionError); return }
            const data = await res.json()
            setMessages((prev) => [...prev, {
                id: data.id, role: "sav", content: data.contenu ?? trimmed,
                createdAt: data.date_creation
                    ? new Date(data.date_creation).toLocaleTimeString(dateLocale, { hour: "2-digit", minute: "2-digit" })
                    : "",
            }])
            setReply("")
            // Le backend flippe déjà waiting_on="customer" sur ce ticket (routers/messages.py) —
            // on recharge juste le ticket pour refléter ce changement, sans le dupliquer ici.
            const ticketRes = await fetch(`/api/tickets/${ticket.id}`)
            if (ticketRes.ok) setTicket(await ticketRes.json())
        } catch {
            setError(t.tickets.actionError)
        } finally {
            setIsSending(false)
        }
    }

    if (isLoadingUser || !user || user.role === "user") return null

    if (isLoading) {
        return <div className="px-8 py-12 text-center text-sm text-muted-foreground">{t.tickets.loading}</div>
    }

    if (notFound) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-3 px-8">
                <p className="text-sm text-muted-foreground">{t.tickets.notFound}</p>
                <Link href="/tickets" className="text-sm text-indigo-600 hover:underline">{t.tickets.backToList}</Link>
            </div>
        )
    }

    if (subscriptionSuspended) {
        return (
            <div className="px-8 py-12 text-center text-sm text-amber-700">{t.tickets.subscriptionSuspended}</div>
        )
    }

    if (!ticket) {
        return <div className="px-8 py-12 text-center text-sm text-red-600">{error ?? t.tickets.loadError}</div>
    }

    const contextMessages = ticket.context_cutoff_message_id
        ? messages.filter((m) => m.id <= ticket.context_cutoff_message_id!)
        : []
    const isUnassigned = !ticket.assigned_agent_id
    const isMine = ticket.assigned_agent_id === user.id

    return (
        <div className="flex flex-col min-h-full bg-muted/50">
            <header className="flex items-center justify-between px-8 py-5 bg-card border-b shadow-sm gap-4 flex-wrap">
                <div className="flex items-center gap-3 min-w-0">
                    <Link href="/tickets" className="p-2 rounded-lg hover:bg-muted text-muted-foreground flex-shrink-0" title={t.tickets.backToList}>
                        <ArrowLeft className="h-4 w-4" />
                    </Link>
                    <div className="min-w-0">
                        <h1 className="text-lg font-bold tracking-tight text-foreground">#{ticket.ticket_number}</h1>
                        <p className="text-xs text-muted-foreground truncate">
                            {ticket.client_username?.startsWith("guest_") ? t.tickets.guest : ticket.client_username || ticket.client_email}
                        </p>
                    </div>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border flex-shrink-0 ${STATUS_STYLES[ticket.status] ?? ""}`}>
                        {{ new: t.tickets.statusNew, in_progress: t.tickets.statusInProgress, resolved: t.tickets.statusResolved, closed: t.tickets.statusClosed }[ticket.status]}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border flex-shrink-0 ${ticket.waiting_on === "us" ? "bg-red-100 text-red-700 border-red-200 font-semibold" : "bg-slate-100 text-slate-500 border-slate-200"}`}>
                        {ticket.waiting_on === "us" ? t.tickets.waitingOnUs : t.tickets.waitingOnCustomer}
                    </span>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                    <Select value={ticket.status} onValueChange={handleStatusChange}>
                        <SelectTrigger className="h-9 w-[140px]"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="new">{t.tickets.statusNew}</SelectItem>
                            <SelectItem value="in_progress">{t.tickets.statusInProgress}</SelectItem>
                            <SelectItem value="resolved">{t.tickets.statusResolved}</SelectItem>
                            <SelectItem value="closed">{t.tickets.statusClosed}</SelectItem>
                        </SelectContent>
                    </Select>
                    <Button type="button" variant="outline" size="sm" onClick={() => void handleWaitingOnToggle()}>
                        {ticket.waiting_on === "us" ? t.tickets.waitingOnCustomer : t.tickets.waitingOnUs}
                    </Button>
                    {isUnassigned && !canManageTeam && (
                        <Button type="button" size="sm" disabled={isTaking} onClick={() => void handleTake()} className="bg-emerald-600 hover:bg-emerald-700">
                            <UserPlus className="h-3.5 w-3.5 mr-1.5" /> {isTaking ? t.tickets.taking : t.tickets.takeTicket}
                        </Button>
                    )}
                    {canManageTeam && (
                        <div className="flex items-center gap-1.5">
                            <Select value={assignTarget} onValueChange={setAssignTarget}>
                                <SelectTrigger className="h-9 w-[160px]"><SelectValue placeholder={t.tickets.chooseAgent} /></SelectTrigger>
                                <SelectContent>
                                    {agents.map((a) => <SelectItem key={a.id} value={String(a.id)}>{a.username}</SelectItem>)}
                                </SelectContent>
                            </Select>
                            <Button type="button" size="sm" disabled={!assignTarget} onClick={() => void handleAssign()}>
                                {isUnassigned ? t.tickets.assignButton : t.tickets.reassignButton}
                            </Button>
                        </div>
                    )}
                </div>
            </header>

            {error && (
                <div className="mx-8 mt-4 flex items-center gap-2 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-700 dark:text-red-400">
                    <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                    {error}
                </div>
            )}

            <div className="p-8 grid gap-5 lg:grid-cols-[320px_1fr] max-w-7xl mx-auto w-full items-start">
                {/* Différenciateur : contexte IA avant transfert */}
                <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                    <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-indigo-600" />
                        <p className="text-sm font-semibold text-foreground">{t.tickets.contextTitle}</p>
                    </div>
                    <div className="p-4 space-y-3">
                        {ticket.reason && (
                            <div>
                                <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">{t.tickets.contextReasonLabel}</p>
                                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${REASON_STYLES[ticket.reason] ?? ""}`}>
                                    {reasonLabel(ticket.reason)}
                                </span>
                            </div>
                        )}
                        {contextMessages.length === 0 ? (
                            <p className="text-xs text-muted-foreground">{t.tickets.contextEmpty}</p>
                        ) : (
                            <div className="space-y-2">
                                {contextMessages.map((m) => (
                                    <div key={m.id} className="text-xs rounded-lg border border-border bg-muted/40 px-3 py-2">
                                        <span className="font-semibold text-muted-foreground">
                                            {m.role === "ai" ? t.tickets.aiAssistant : t.tickets.client}
                                        </span>
                                        <p className="text-foreground mt-0.5">{m.content}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Conversation complète */}
                <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden flex flex-col">
                    <div className="px-4 py-3 border-b border-border">
                        <p className="text-sm font-semibold text-foreground">{t.tickets.conversationTitle}</p>
                    </div>
                    <div className="p-4 space-y-4 max-h-[520px] overflow-y-auto">
                        {messages.map((m) => (
                            <div key={m.id} className={`flex ${m.role === "sav" ? "justify-end" : "justify-start"}`}>
                                <div className={`max-w-[80%] flex flex-col ${m.role === "sav" ? "items-end" : "items-start"}`}>
                                    <div className={`rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                                        m.role === "sav" ? "bg-emerald-600 text-white" : m.role === "user" ? "bg-indigo-600 text-white" : "bg-card border-2 border-border text-foreground"
                                    }`}>
                                        {m.content}
                                    </div>
                                    <span className="text-[10px] text-muted-foreground font-bold uppercase tracking-tighter px-2 mt-1">
                                        {m.role === "sav" ? t.tickets.you : m.role === "user" ? t.tickets.client : t.tickets.aiAssistant} • {m.createdAt}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="border-t border-border p-4">
                        <form onSubmit={(e) => { e.preventDefault(); void handleSendReply() }} className="relative">
                            <Input
                                value={reply}
                                onChange={(e) => setReply(e.target.value)}
                                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void handleSendReply() } }}
                                placeholder={t.tickets.replyPlaceholder}
                                disabled={isSending || (!isMine && !canManageTeam && !isUnassigned)}
                                className="h-12 pl-4 pr-24 rounded-xl border-2 border-border focus-visible:ring-emerald-500"
                            />
                            <div className="absolute right-1.5 top-1.5">
                                <Button type="submit" size="sm" disabled={!reply.trim() || isSending} className="h-9 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700">
                                    <Send className="h-3.5 w-3.5 mr-1.5" /> {t.tickets.send}
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    )
}
