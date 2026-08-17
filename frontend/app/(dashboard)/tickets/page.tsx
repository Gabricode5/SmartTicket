"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Ticket as TicketIcon, ChevronLeft, ChevronRight, Search, Inbox, User as UserIcon } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useLocale } from "@/lib/i18n/LocaleContext"
import type { Ticket, TicketListResponse } from "@/components/dashboard/types"

const PAGE_SIZE = 20

// Convention établie côté backend (routers/sessions.py::create_guest_session) : un compte
// invité a toujours un username "guest_{suffixe}" — aucun flag "is_guest" n'est renvoyé par
// GET /v1/tickets, donc on le détecte via ce préfixe plutôt que d'étendre le backend pour ça.
const isGuestUsername = (username: string | null | undefined) => Boolean(username?.startsWith("guest_"))

const STATUS_STYLES: Record<string, string> = {
    new: "bg-sky-100 text-sky-700 border-sky-200",
    in_progress: "bg-amber-100 text-amber-700 border-amber-200",
    resolved: "bg-emerald-100 text-emerald-700 border-emerald-200",
    closed: "bg-slate-100 text-slate-600 border-slate-200",
}

const WAITING_ON_STYLES: Record<string, string> = {
    // "À répondre" doit ressortir clairement — c'est ce qui attend l'action de l'agent.
    us: "bg-red-100 text-red-700 border-red-200 font-semibold",
    customer: "bg-slate-100 text-slate-500 border-slate-200",
}

const PRIORITY_STYLES: Record<string, string> = {
    normal: "bg-slate-100 text-slate-600 border-slate-200",
    urgent: "bg-red-100 text-red-700 border-red-200 font-semibold",
}

export default function TicketsListPage() {
    const router = useRouter()
    const { user, isLoading: isLoadingUser } = useCurrentUser()
    const { messages: t, locale } = useLocale()
    const dateLocale = locale === "fr" ? "fr-FR" : "en-US"

    const [tickets, setTickets] = useState<Ticket[]>([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [subscriptionSuspended, setSubscriptionSuspended] = useState(false)

    const [statusFilter, setStatusFilter] = useState<string>("")
    const [waitingOnFilter, setWaitingOnFilter] = useState<string>("")
    const [priorityFilter, setPriorityFilter] = useState<string>("")
    const [quickFilter, setQuickFilter] = useState<"queue" | "mine" | null>(null)
    const [searchInput, setSearchInput] = useState("")
    const [searchQuery, setSearchQuery] = useState("")

    useEffect(() => {
        if (!isLoadingUser && user && user.role === "user") router.replace("/dashboard")
    }, [isLoadingUser, user, router])

    useEffect(() => {
        if (!user || user.role === "user") return

        let cancelled = false
        async function loadTickets() {
            setIsLoading(true)
            setError(null)
            setSubscriptionSuspended(false)
            try {
                const params = new URLSearchParams()
                params.set("page", String(page))
                params.set("page_size", String(PAGE_SIZE))
                let url = "/api/tickets"
                if (searchQuery) {
                    params.set("q", searchQuery)
                    url = "/api/tickets/search"
                } else {
                    if (statusFilter) params.set("status", statusFilter)
                    if (waitingOnFilter) params.set("waiting_on", waitingOnFilter)
                    if (priorityFilter) params.set("priority", priorityFilter)
                    if (quickFilter === "queue") params.set("unassigned", "true")
                    else if (quickFilter === "mine" && user) params.set("assigned_agent_id", String(user.id))
                }
                const res = await fetch(`${url}?${params.toString()}`)
                if (cancelled) return
                if (res.status === 401) { setError(t.tickets.sessionExpired); return }
                if (res.status === 402) { setSubscriptionSuspended(true); return }
                if (!res.ok) { setError(t.tickets.loadError); return }
                const data: TicketListResponse = await res.json()
                if (cancelled) return
                setTickets(data.items)
                setTotal(data.total)
            } catch {
                if (!cancelled) setError(t.tickets.loadError)
            } finally {
                if (!cancelled) setIsLoading(false)
            }
        }
        loadTickets()
        return () => { cancelled = true }
        // eslint-disable-next-line react-hooks/exhaustive-deps -- t change avec la langue, ne doit pas redéclencher un fetch
    }, [user, page, statusFilter, waitingOnFilter, priorityFilter, quickFilter, searchQuery])

    const resetToPageOne = () => setPage(1)

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

    const statusLabel = (status: string) => ({
        new: t.tickets.statusNew, in_progress: t.tickets.statusInProgress,
        resolved: t.tickets.statusResolved, closed: t.tickets.statusClosed,
    }[status] ?? status)

    const waitingOnLabel = (waitingOn: string) => (waitingOn === "us" ? t.tickets.waitingOnUs : t.tickets.waitingOnCustomer)

    const priorityLabel = (priority: string) => (priority === "urgent" ? t.tickets.priorityUrgent : t.tickets.priorityNormal)

    if (isLoadingUser || !user || user.role === "user") return null

    return (
        <div className="flex flex-col min-h-full bg-muted/50">
            <header className="flex items-center justify-between px-8 py-5 bg-card border-b shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-600 shadow-sm">
                        <TicketIcon className="h-5 w-5 text-white" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold tracking-tight text-foreground">{t.tickets.title}</h1>
                        <p className="text-xs text-muted-foreground">{t.tickets.subtitle}</p>
                    </div>
                </div>
            </header>

            <div className="p-8 space-y-5 max-w-7xl mx-auto w-full">
                {error && (
                    <div className="flex items-center gap-2 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-700 dark:text-red-400">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                        {error}
                    </div>
                )}
                {subscriptionSuspended && (
                    <div className="flex items-center gap-2 rounded-lg border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
                        <div className="w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                        {t.tickets.subscriptionSuspended}
                    </div>
                )}

                {/* Filtres */}
                <div className="bg-card rounded-xl border border-border shadow-sm p-4 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                        <Button
                            type="button"
                            variant={quickFilter === "queue" ? "default" : "outline"}
                            size="sm"
                            onClick={() => { setQuickFilter(quickFilter === "queue" ? null : "queue"); resetToPageOne() }}
                        >
                            <Inbox className="h-3.5 w-3.5 mr-1.5" /> {t.tickets.queueFilter}
                        </Button>
                        <Button
                            type="button"
                            variant={quickFilter === "mine" ? "default" : "outline"}
                            size="sm"
                            onClick={() => { setQuickFilter(quickFilter === "mine" ? null : "mine"); resetToPageOne() }}
                        >
                            <UserIcon className="h-3.5 w-3.5 mr-1.5" /> {t.tickets.mineFilter}
                        </Button>

                        <form
                            className="relative flex-1 min-w-[200px]"
                            onSubmit={(e) => { e.preventDefault(); setSearchQuery(searchInput.trim()); resetToPageOne() }}
                        >
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                            <Input
                                value={searchInput}
                                onChange={(e) => setSearchInput(e.target.value)}
                                placeholder={t.tickets.searchPlaceholder}
                                className="pl-9 h-9"
                            />
                        </form>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                        <Select value={statusFilter || "all"} onValueChange={(v) => { setStatusFilter(v === "all" ? "" : v); resetToPageOne() }}>
                            <SelectTrigger className="h-9 w-[160px]"><SelectValue placeholder={t.tickets.allStatuses} /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">{t.tickets.allStatuses}</SelectItem>
                                <SelectItem value="new">{t.tickets.statusNew}</SelectItem>
                                <SelectItem value="in_progress">{t.tickets.statusInProgress}</SelectItem>
                                <SelectItem value="resolved">{t.tickets.statusResolved}</SelectItem>
                                <SelectItem value="closed">{t.tickets.statusClosed}</SelectItem>
                            </SelectContent>
                        </Select>

                        <Select value={waitingOnFilter || "all"} onValueChange={(v) => { setWaitingOnFilter(v === "all" ? "" : v); resetToPageOne() }}>
                            <SelectTrigger className="h-9 w-[160px]"><SelectValue placeholder={t.tickets.allWaitingOn} /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">{t.tickets.allWaitingOn}</SelectItem>
                                <SelectItem value="us">{t.tickets.waitingOnUs}</SelectItem>
                                <SelectItem value="customer">{t.tickets.waitingOnCustomer}</SelectItem>
                            </SelectContent>
                        </Select>

                        <Select value={priorityFilter || "all"} onValueChange={(v) => { setPriorityFilter(v === "all" ? "" : v); resetToPageOne() }}>
                            <SelectTrigger className="h-9 w-[160px]"><SelectValue placeholder={t.tickets.allPriorities} /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">{t.tickets.allPriorities}</SelectItem>
                                <SelectItem value="normal">{t.tickets.priorityNormal}</SelectItem>
                                <SelectItem value="urgent">{t.tickets.priorityUrgent}</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Liste */}
                <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                    <div className="px-5 py-3 border-b border-border flex items-center justify-between">
                        <p className="text-sm font-semibold text-foreground">{t.tickets.resultsCount(total)}</p>
                    </div>

                    {isLoading ? (
                        <div className="px-5 py-12 text-center text-sm text-muted-foreground">{t.tickets.loading}</div>
                    ) : tickets.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-40 gap-2 px-5">
                            <TicketIcon className="h-8 w-8 text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">{t.tickets.empty}</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-slate-50">
                            {tickets.map((ticket) => {
                                const clientLabel = isGuestUsername(ticket.client_username)
                                    ? t.tickets.guest
                                    : ticket.client_username || ticket.client_email || "—"
                                return (
                                    <Link
                                        key={ticket.id}
                                        href={`/tickets/${ticket.id}`}
                                        className="flex items-center gap-4 px-5 py-3 hover:bg-muted/80 transition-colors"
                                    >
                                        <span className="text-xs font-mono text-muted-foreground w-14 flex-shrink-0">#{ticket.ticket_number}</span>
                                        <span className="text-sm font-medium text-foreground flex-1 min-w-0 truncate">{clientLabel}</span>
                                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border flex-shrink-0 ${STATUS_STYLES[ticket.status] ?? ""}`}>
                                            {statusLabel(ticket.status)}
                                        </span>
                                        <span className={`text-[10px] px-2 py-0.5 rounded-full border flex-shrink-0 ${WAITING_ON_STYLES[ticket.waiting_on] ?? ""}`}>
                                            {waitingOnLabel(ticket.waiting_on)}
                                        </span>
                                        <span className={`text-[10px] px-2 py-0.5 rounded-full border flex-shrink-0 ${PRIORITY_STYLES[ticket.priority] ?? ""}`}>
                                            {priorityLabel(ticket.priority)}
                                        </span>
                                        <span className="text-xs text-muted-foreground w-32 flex-shrink-0 truncate">
                                            {ticket.assigned_agent_username || t.tickets.unassigned}
                                        </span>
                                        <span className="text-xs text-muted-foreground w-32 flex-shrink-0 text-right">
                                            {new Date(ticket.updated_at).toLocaleString(dateLocale, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                                        </span>
                                    </Link>
                                )
                            })}
                        </div>
                    )}

                    {totalPages > 1 && (
                        <div className="flex items-center justify-between px-5 py-3 border-t border-border">
                            <button onClick={() => setPage((p) => p - 1)} disabled={page <= 1} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                <ChevronLeft className="h-4 w-4" />
                            </button>
                            <span className="text-xs text-muted-foreground">{t.tickets.pageOf(page, totalPages)}</span>
                            <button onClick={() => setPage((p) => p + 1)} disabled={page >= totalPages} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                <ChevronRight className="h-4 w-4" />
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
