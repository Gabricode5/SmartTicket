"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Search, MessageSquare, Zap, Clock, Star, TrendingUp, Bot, Headphones, ChevronLeft, ChevronRight } from "lucide-react"
import type { SessionItem, SessionSearchResult } from "./types"
import { renderSnippet } from "./searchSnippet"
import { groupByDate } from "./dateGrouping"

export default function UserDashboard({ userId }: { userId: number }) {
    const router = useRouter()
    const [userSessions, setUserSessions] = useState<SessionItem[]>([])
    const [userQuery, setUserQuery] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [closingSessionId, setClosingSessionId] = useState<number | null>(null)
    const [sessionsPage, setSessionsPage] = useState(1)
    const [searchResults, setSearchResults] = useState<SessionSearchResult[] | null>(null)
    const [isSearching, setIsSearching] = useState(false)

    const PAGE_SIZE = 10

    useEffect(() => {
        async function loadSessions() {
            setIsLoading(true)
            setError(null)
            try {
                const res = await fetch(`/api/sessions?user_id=${userId}`)
                if (res.status === 401) { setError("Session expirée. Veuillez vous reconnecter."); return }
                if (!res.ok) { setError("Impossible de charger vos conversations."); return }
                setUserSessions(await res.json())
            } catch {
                setError("Erreur réseau.")
            } finally {
                setIsLoading(false)
            }
        }
        loadSessions()
    }, [userId])

    // Full-text search (débounced) sur le contenu des messages + titres, côté serveur.
    useEffect(() => {
        const trimmed = userQuery.trim()
        if (!trimmed) {
            setSearchResults(null)
            setIsSearching(false)
            return
        }
        setIsSearching(true)
        const timeoutId = setTimeout(async () => {
            try {
                const res = await fetch(`/api/sessions/search?user_id=${userId}&q=${encodeURIComponent(trimmed)}`)
                setSearchResults(res.ok ? await res.json() : [])
            } catch {
                setSearchResults([])
            } finally {
                setIsSearching(false)
            }
        }, 300)
        return () => clearTimeout(timeoutId)
    }, [userQuery, userId])

    const handleCloseSession = async (session: SessionItem) => {
        const confirmed = window.confirm(`Clôturer la session #${session.id} ?`)
        if (!confirmed) return
        setClosingSessionId(session.id)
        try {
            const res = await fetch(`/api/sessions/${session.id}/close`, { method: "POST" })
            if (!res.ok) {
                const data = await res.json()
                setError(data?.detail || "Impossible de clôturer la session.")
                return
            }
            const refresh = await fetch(`/api/sessions?user_id=${userId}`)
            if (refresh.ok) setUserSessions(await refresh.json())
        } catch {
            setError("Erreur réseau.")
        } finally {
            setClosingSessionId(null)
        }
    }

    const isSearchMode = userQuery.trim().length > 0

    const totalSessions = userSessions.length
    const closedSessions = userSessions.filter((s) => s.status === "closed").length
    const openSessions = totalSessions - closedSessions
    const closureRate = totalSessions > 0 ? `${Math.round((closedSessions / totalSessions) * 100)}%` : "0%"
    const lastSessionDate = userSessions
        .map((s) => s.date_creation)
        .filter((d): d is string => Boolean(d))
        .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0]
    const lastActivityLabel = lastSessionDate
        ? new Date(lastSessionDate).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })
        : "Aucune"

    return (
        <div className="flex flex-col min-h-full">
            <header className="flex items-center justify-between px-8 py-5 bg-background border-b sticky top-0 z-10">
                <h1 className="text-2xl font-bold tracking-tight">Tableau de bord</h1>
                <div className="relative w-96 hidden md:block">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        type="search"
                        placeholder="Rechercher des conversations..."
                        value={userQuery}
                        onChange={(e) => { setUserQuery(e.target.value); setSessionsPage(1) }}
                        className="pl-9 bg-muted/20 border-muted-foreground/20 focus-visible:ring-offset-0 focus-visible:bg-background transition-colors"
                    />
                </div>
            </header>

            <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">
                {error && (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>
                )}

                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Total Conversations</CardTitle>
                            <MessageSquare className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{totalSessions}</div>
                            <p className="text-xs text-muted-foreground flex items-center mt-1">
                                <TrendingUp className="h-3 w-3 text-green-500 mr-1" />
                                <span className="text-green-500 font-medium">Activité personnelle</span>
                            </p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Sessions clôturées</CardTitle>
                            <Zap className="h-4 w-4 text-yellow-500" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{closureRate}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                {closedSessions} conversation{closedSessions > 1 ? "s" : ""} terminée{closedSessions > 1 ? "s" : ""}
                            </p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Conversations ouvertes</CardTitle>
                            <Clock className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{openSessions}</div>
                            <p className="text-xs text-muted-foreground mt-1">Encore en attente de clôture</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Dernière activité</CardTitle>
                            <Star className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{lastActivityLabel}</div>
                            <p className="text-xs text-muted-foreground mt-1">Basé sur la date de vos sessions</p>
                        </CardContent>
                    </Card>
                </div>

                <div className="grid gap-6 lg:grid-cols-7">
                    <Card className="col-span-4 lg:col-span-5">
                        <CardHeader>
                            <CardTitle>Vos conversations</CardTitle>
                            <CardDescription>Vos discussions personnelles uniquement.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-6">
                                {isSearchMode ? (
                                    isSearching ? (
                                        <div className="text-sm text-muted-foreground">Recherche...</div>
                                    ) : !searchResults || searchResults.length === 0 ? (
                                        <div className="text-sm text-muted-foreground">Aucun résultat pour « {userQuery.trim()} ».</div>
                                    ) : (
                                        searchResults.map((session) => (
                                            <div
                                                key={session.id}
                                                role="button"
                                                tabIndex={0}
                                                onClick={() => router.push(`/ai-assistant/${session.id}`)}
                                                onKeyDown={(e) => {
                                                    if (e.key === "Enter" || e.key === " ") {
                                                        e.preventDefault()
                                                        router.push(`/ai-assistant/${session.id}`)
                                                    }
                                                }}
                                                className="w-full flex items-start justify-between rounded-md border border-transparent hover:border-muted hover:bg-muted/30 px-3 py-2 transition cursor-pointer"
                                            >
                                                <div className="min-w-0">
                                                    <p className="text-sm font-medium leading-none">
                                                        {session.title || "Nouvelle conversation"}
                                                    </p>
                                                    {session.snippet && (
                                                        <p className="text-sm text-muted-foreground mt-1.5">
                                                            {renderSnippet(session.snippet)}
                                                        </p>
                                                    )}
                                                </div>
                                                <div className="flex flex-col items-end gap-1 flex-shrink-0 ml-4">
                                                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                                                        {session.date_creation
                                                            ? new Date(session.date_creation).toLocaleDateString("fr-FR")
                                                            : "—"}
                                                    </span>
                                                    <Badge variant="secondary" className={`${
                                                        session.status === "closed" ? "bg-slate-200 text-slate-700"
                                                        : session.status === "transferred" ? "bg-amber-100 text-amber-700"
                                                        : "bg-emerald-100 text-emerald-700"
                                                    } border-0`}>
                                                        {session.status === "closed" ? "Clôturée" : session.status === "transferred" ? "Transférée" : "Ouverte"}
                                                    </Badge>
                                                </div>
                                            </div>
                                        ))
                                    )
                                ) : isLoading ? (
                                    <div className="text-sm text-muted-foreground">Chargement...</div>
                                ) : userSessions.length === 0 ? (
                                    <div className="text-sm text-muted-foreground">Aucune conversation.</div>
                                ) : (
                                    groupByDate(userSessions.slice((sessionsPage - 1) * PAGE_SIZE, sessionsPage * PAGE_SIZE)).map((group) => (
                                        <div key={group.label} className="space-y-1">
                                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-3 pb-1">
                                                {group.label}
                                            </p>
                                            {group.items.map((session) => (
                                                <div
                                                    key={session.id}
                                                    role="button"
                                                    tabIndex={0}
                                                    onClick={() => router.push(`/ai-assistant/${session.id}`)}
                                                    onKeyDown={(e) => {
                                                        if (e.key === "Enter" || e.key === " ") {
                                                            e.preventDefault()
                                                            router.push(`/ai-assistant/${session.id}`)
                                                        }
                                                    }}
                                                    className="w-full flex items-center justify-between rounded-md border border-transparent hover:border-muted hover:bg-muted/30 px-3 py-2 transition cursor-pointer"
                                                >
                                                    <div className="flex items-center gap-4">
                                                        <Avatar className="h-10 w-10 border">
                                                            <AvatarFallback>
                                                                {(session.title || "NC").substring(0, 2).toUpperCase()}
                                                            </AvatarFallback>
                                                        </Avatar>
                                                        <div className="text-left">
                                                            <p className="text-sm font-medium leading-none">
                                                                {session.title || "Nouvelle conversation"}
                                                            </p>
                                                            <p className="text-sm text-muted-foreground line-clamp-1 mt-1">
                                                                Session #{session.id}
                                                            </p>
                                                        </div>
                                                    </div>
                                                    <div className="flex flex-col items-end gap-1">
                                                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                                                            {session.date_creation
                                                                ? new Date(session.date_creation).toLocaleDateString("fr-FR")
                                                                : "—"}
                                                        </span>
                                                        <Badge variant="secondary" className={`${
                                                            session.status === "closed" ? "bg-slate-200 text-slate-700"
                                                            : session.status === "transferred" ? "bg-amber-100 text-amber-700"
                                                            : "bg-emerald-100 text-emerald-700"
                                                        } border-0`}>
                                                            {session.status === "closed" ? "Clôturée" : session.status === "transferred" ? "Transférée" : "Ouverte"}
                                                        </Badge>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={(e) => { e.stopPropagation(); handleCloseSession(session) }}
                                                            disabled={closingSessionId === session.id || session.status === "closed"}
                                                        >
                                                            {closingSessionId === session.id ? "..." : "Clôturer"}
                                                        </Button>
                                                        {session.status === "transferred" && session.has_sav_reply ? (
                                                            <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 border-0">
                                                                <Headphones className="h-3 w-3 mr-1" />
                                                                Agent SAV a répondu
                                                            </Badge>
                                                        ) : session.status === "transferred" ? (
                                                            <Badge variant="secondary" className="bg-amber-100 text-amber-700 border-0">
                                                                <Headphones className="h-3 w-3 mr-1" />
                                                                En attente SAV
                                                            </Badge>
                                                        ) : (
                                                            <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/15 border-0">
                                                                <Bot className="h-3 w-3 mr-1" />
                                                                IA Autonome
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ))
                                )}
                                {!isSearchMode && Math.ceil(userSessions.length / PAGE_SIZE) > 1 && (
                                    <div className="flex items-center justify-between pt-2 border-t">
                                        <button
                                            onClick={() => setSessionsPage(p => p - 1)}
                                            disabled={sessionsPage <= 1}
                                            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
                                        >
                                            <ChevronLeft className="h-4 w-4" /> Précédent
                                        </button>
                                        <span className="text-sm text-muted-foreground">
                                            {sessionsPage} / {Math.ceil(userSessions.length / PAGE_SIZE)}
                                        </span>
                                        <button
                                            onClick={() => setSessionsPage(p => p + 1)}
                                            disabled={sessionsPage >= Math.ceil(userSessions.length / PAGE_SIZE)}
                                            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
                                        >
                                            Suivant <ChevronRight className="h-4 w-4" />
                                        </button>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}
