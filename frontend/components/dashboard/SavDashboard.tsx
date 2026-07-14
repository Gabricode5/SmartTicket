"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Bot, Headphones, MessageSquare, Send } from "lucide-react"
import { REASON_STYLES, type MessageItem, type TransferredSession } from "./types"
import { groupByDate } from "./dateGrouping"
import { useLocale } from "@/lib/i18n/LocaleContext"

export default function SavDashboard() {
    const { messages: t, locale } = useLocale()
    const dateLocale = locale === "fr" ? "fr-FR" : "en-US"
    const reasonLabel = (reason: string | null | undefined) => (reason ? t.common.reasons[reason as keyof typeof t.common.reasons] ?? reason : reason)
    const [transferredSessions, setTransferredSessions] = useState<TransferredSession[]>([])
    const [selectedSession, setSelectedSession] = useState<TransferredSession | null>(null)
    const [messages, setMessages] = useState<MessageItem[]>([])
    const [reply, setReply] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [isResolving, setIsResolving] = useState(false)

    useEffect(() => {
        async function loadTransferred() {
            setIsLoading(true)
            try {
                const res = await fetch("/api/sessions/transferred")
                if (res.ok) setTransferredSessions(await res.json())
            } catch { /* ignore */ } finally {
                setIsLoading(false)
            }
        }
        loadTransferred()
    }, [])

    const handleSelectSession = async (s: TransferredSession) => {
        setSelectedSession(s)
        setMessages([])
        try {
            const res = await fetch(`/api/messages?session_id=${s.id}`)
            if (!res.ok) return
            const data = await res.json()
            if (!Array.isArray(data)) return
            setMessages(data.map((item: { id?: number | string; type_envoyeur: string; contenu?: string | null; date_creation?: string | null }) => ({
                id: String(item.id ?? Date.now()),
                role: item.type_envoyeur === "sav" ? "sav" : item.type_envoyeur === "ai" ? "ai" : "user",
                content: item.contenu ?? "",
                createdAt: item.date_creation
                    ? new Date(item.date_creation).toLocaleTimeString(dateLocale, { hour: "2-digit", minute: "2-digit" })
                    : "",
            })))
        } catch { /* ignore */ }
    }

    const handleSendReply = async () => {
        const trimmed = reply.trim()
        if (!trimmed || !selectedSession) return
        try {
            const res = await fetch("/api/messages", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id_session: selectedSession.id, type_envoyeur: "sav", contenu: trimmed }),
            })
            if (!res.ok) return
            const data = await res.json()
            setMessages((prev) => [...prev, {
                id: String(data.id),
                role: "sav",
                content: data.contenu ?? trimmed,
                createdAt: data.date_creation
                    ? new Date(data.date_creation).toLocaleTimeString(dateLocale, { hour: "2-digit", minute: "2-digit" })
                    : "",
            }])
            setReply("")
        } catch { /* ignore */ }
    }

    const handleResolve = async () => {
        if (!selectedSession || isResolving) return
        setIsResolving(true)
        try {
            const res = await fetch(`/api/sessions/${selectedSession.id}/resolve`, { method: "POST" })
            if (res.ok) {
                setTransferredSessions((prev) => prev.filter((s) => s.id !== selectedSession.id))
                setSelectedSession(null)
                setMessages([])
            }
        } catch { /* ignore */ } finally {
            setIsResolving(false)
        }
    }

    return (
        <div className="flex h-full bg-muted/30">
            {/* Queue sidebar */}
            <div className="w-80 flex-shrink-0 border-r border-border bg-card flex flex-col">
                <div className="h-16 px-5 flex items-center gap-3 border-b border-border shrink-0">
                    <div className="w-9 h-9 rounded-lg bg-emerald-600 flex items-center justify-center shadow-sm">
                        <Headphones className="h-5 w-5 text-white" />
                    </div>
                    <div className="min-w-0 flex-1">
                        <h1 className="text-sm font-bold text-foreground truncate">{t.sav.queueTitle}</h1>
                        <p className="text-[11px] text-muted-foreground">{t.sav.waitingCount(transferredSessions.length)}</p>
                    </div>
                    <Badge className="bg-amber-50 text-amber-600 border-amber-100 text-xs font-semibold">
                        {transferredSessions.length}
                    </Badge>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {isLoading ? (
                        <div className="px-5 py-12 text-center text-sm text-muted-foreground">{t.sav.loading}</div>
                    ) : transferredSessions.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-40 gap-2 px-5">
                            <Headphones className="h-8 w-8 text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">{t.sav.noTransfers}</p>
                        </div>
                    ) : (
                        groupByDate(transferredSessions, new Date(), t.common.dateGroups, dateLocale).map((group) => (
                            <div key={group.label}>
                                <p className="px-4 pt-3 pb-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                                    {group.label}
                                </p>
                                {group.items.map((s) => (
                                    <button
                                        key={s.id}
                                        onClick={() => handleSelectSession(s)}
                                        className={`w-full text-left px-4 py-3 transition-colors border-b border-border ${selectedSession?.id === s.id ? "bg-emerald-50/70 border-l-2 border-l-emerald-500" : "hover:bg-muted border-l-2 border-l-transparent"}`}
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="w-9 h-9 rounded-full bg-indigo-50 flex items-center justify-center flex-shrink-0 text-xs font-bold text-indigo-600 border-2 border-indigo-100">
                                                {s.username.charAt(0).toUpperCase()}
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <div className="text-sm font-medium text-foreground truncate">{s.username}</div>
                                                <div className="text-xs text-muted-foreground truncate">{s.title || t.sav.untitled}</div>
                                                <div className="flex items-center gap-1.5 mt-1">
                                                    {s.transfer_reason && (
                                                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${REASON_STYLES[s.transfer_reason] ?? "bg-muted text-muted-foreground border-border"}`}>
                                                            {reasonLabel(s.transfer_reason)}
                                                        </span>
                                                    )}
                                                    <span className="text-[10px] text-muted-foreground">#{s.id}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Chat area */}
            <div className="flex-1 flex flex-col min-w-0">
                <header className="h-16 border-b bg-card flex items-center justify-between px-6 shrink-0 shadow-sm">
                    {selectedSession ? (
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-indigo-50 flex items-center justify-center text-sm font-bold text-indigo-600 border-2 border-indigo-100">
                                {selectedSession.username.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <h2 className="font-bold text-sm text-foreground">
                                    {selectedSession.username}{" "}
                                    <span className="text-muted-foreground font-normal ml-1">#{selectedSession.id}</span>
                                </h2>
                                <p className="text-[11px] font-medium flex items-center gap-1 text-amber-600">
                                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                                    {t.sav.transferredReason(reasonLabel(selectedSession.transfer_reason) ?? selectedSession.transfer_reason ?? "–")}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center">
                                <Headphones className="h-5 w-5 text-emerald-600" />
                            </div>
                            <div>
                                <h2 className="font-bold text-sm text-foreground">{t.sav.supportTitle}</h2>
                                <p className="text-[11px] font-medium text-muted-foreground">{t.sav.selectConversation}</p>
                            </div>
                        </div>
                    )}
                    <div className="flex items-center gap-2">
                        {selectedSession && (
                            <button
                                onClick={() => void handleResolve()}
                                disabled={isResolving}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors text-[11px] font-bold uppercase disabled:opacity-50"
                            >
                                <Bot className="h-3.5 w-3.5" />
                                {isResolving ? t.sav.resolving : t.sav.resolveToAi}
                            </button>
                        )}
                        <Badge className="bg-emerald-50 text-emerald-700 hover:bg-emerald-50 border border-emerald-200 gap-1 text-[10px] py-1">
                            <Headphones className="h-3 w-3" /> {t.sav.agentBadge}
                        </Badge>
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto p-6">
                    {!selectedSession ? (
                        <div className="flex flex-col items-center justify-center h-full max-w-md mx-auto space-y-4">
                            <div className="bg-emerald-600 w-16 h-16 rounded-2xl flex items-center justify-center shadow-xl shadow-emerald-100">
                                <Headphones className="h-9 w-9 text-white" />
                            </div>
                            <h1 className="text-2xl font-black text-foreground tracking-tight text-center">{t.sav.emptyStateTitle}</h1>
                            <p className="text-muted-foreground text-sm text-center">{t.sav.emptyStateDesc}</p>
                        </div>
                    ) : messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full gap-2">
                            <MessageSquare className="h-8 w-8 text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">{t.sav.loadingMessages}</p>
                        </div>
                    ) : (
                        <div className="space-y-6 max-w-4xl mx-auto">
                            {messages.map((m) => (
                                <div key={m.id} className={`flex ${m.role === "sav" ? "justify-end" : "justify-start"}`}>
                                    <div className={`max-w-[80%] flex flex-col ${m.role === "sav" ? "items-end" : "items-start"}`}>
                                        <div className={`rounded-2xl px-5 py-3 text-sm shadow-sm ${
                                            m.role === "sav"
                                                ? "bg-emerald-600 text-white"
                                                : m.role === "user"
                                                ? "bg-indigo-600 text-white"
                                                : "bg-card border-2 border-border text-foreground"
                                        }`}>
                                            {m.content}
                                        </div>
                                        <span className="text-[10px] text-muted-foreground font-bold uppercase tracking-tighter px-2 mt-1">
                                            {m.role === "sav" ? t.sav.you : m.role === "user" ? t.sav.client : t.sav.aiAssistant} • {m.createdAt}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="bg-card border-t border-border shadow-[0_-4px_20px_rgba(0,0,0,0.03)]">
                    <div className="p-6">
                        <div className="max-w-4xl mx-auto">
                            <form
                                onSubmit={(e) => { e.preventDefault(); void handleSendReply() }}
                                className="relative group"
                            >
                                <Input
                                    value={reply}
                                    onChange={(e) => setReply(e.target.value)}
                                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void handleSendReply() } }}
                                    placeholder={selectedSession ? t.sav.replyPlaceholder : t.sav.replyPlaceholderDisabled}
                                    disabled={!selectedSession}
                                    className="h-14 pl-6 pr-24 rounded-2xl border-2 border-border focus-visible:ring-emerald-500 bg-muted/30 transition-all text-base"
                                />
                                <div className="absolute right-2 top-2">
                                    <Button
                                        type="submit"
                                        disabled={!selectedSession || !reply.trim()}
                                        size="sm"
                                        className="h-10 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 shadow-lg shadow-emerald-100 transition-all"
                                    >
                                        <Send className="h-4 w-4 mr-2" /> {t.sav.send}
                                    </Button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
