"use client"

import { useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Card } from "@/components/ui/card"
import {
    MoreVertical,
    Search,
    FileText,
    Smile,
    Send,
    Bot,
    MessageCircle,
    Zap,
    Sparkles,
    ThumbsUp,
    ThumbsDown,
    Headphones,
    X,
} from "lucide-react"
import { Streamdown } from "streamdown"

type ChatMessage = {
    id: string
    role: "user" | "ai" | "sav"
    content: string
    createdAt: string
    feedback?: 1 | -1 | null
}

type BackendChatMessage = {
    id?: number | string
    type_envoyeur: "user" | "ai" | "sav"
    contenu?: string | null
    date_creation?: string | null
    feedback?: number | null
}

function makeId(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

const SUGGESTIONS = [
    {
        title: "Remboursement Stripe",
        desc: "Depuis le Dashboard Stripe",
        icon: <Smile className="h-4 w-4 text-amber-500" />,
        prompt: "Comment rembourser un client depuis le Dashboard Stripe ?"
    },
    {
        title: "Annuler un remboursement",
        desc: "Remboursement déjà initié",
        icon: <FileText className="h-4 w-4 text-blue-500" />,
        prompt: "Peut-on annuler un remboursement déjà initié ?"
    },
    {
        title: "Erreur carte ou CVV",
        desc: "Paiement refusé côté client",
        icon: <MessageCircle className="h-4 w-4 text-emerald-500" />,
        prompt: "Que faire si un client entre un mauvais numéro de carte ou un CVV incorrect ?"
    },
    {
        title: "Délai de litige",
        desc: "Réponse à un dispute",
        icon: <Zap className="h-4 w-4 text-purple-500" />,
        prompt: "Combien de temps ai-je pour répondre à un litige ?"
    },
]

const TRANSFER_REASONS = [
    { key: "technique", label: "Technique", color: "bg-sky-100 text-sky-700 border-sky-200 hover:bg-sky-200" },
    { key: "complexe", label: "Complexe", color: "bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-200" },
    { key: "sensible", label: "Sensible", color: "bg-red-100 text-red-700 border-red-200 hover:bg-red-200" },
    { key: "autre", label: "Autre", color: "bg-violet-100 text-violet-700 border-violet-200 hover:bg-violet-200" },
]

export default function AiAssistantPage() {
    const params = useParams()
    const router = useRouter()
    const sessionId = Array.isArray(params.id) ? params.id[0] : params.id
    const sessionIdNumber = Number(sessionId)

    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [input, setInput] = useState("")
    const [isSending, setIsSending] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [aiEnabled, setAiEnabled] = useState(true)
    const [username, setUsername] = useState("Utilisateur")
    const [isClosed, setIsClosed] = useState(false)
    const [isTransferred, setIsTransferred] = useState(false)
    const [showTransferPanel, setShowTransferPanel] = useState(false)
    const [isTransferring, setIsTransferring] = useState(false)
    const bottomRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
        const role = localStorage.getItem("user_role")
        if (role === "sav" || role === "admin") {
            router.replace("/")
        }
    }, [router])

    useEffect(() => {
        const storedName = localStorage.getItem("username")
        if (storedName) setUsername(storedName)
    }, [])

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages, isSending])

    useEffect(() => {
        async function loadMessages() {
            if (!Number.isFinite(sessionIdNumber)) return
            try {
                const response = await fetch(`/api/messages?session_id=${sessionIdNumber}`)
                if (response.status === 401) {
                    setError("Session expirée. Veuillez vous reconnecter.")
                    return
                }
                if (!response.ok) return
                const data = await response.json()
                if (!Array.isArray(data)) return

                const normalized: ChatMessage[] = (data as BackendChatMessage[]).map((item) => ({
                    id: String(item.id ?? makeId()),
                    role: item.type_envoyeur === "ai" ? "ai" : item.type_envoyeur === "sav" ? "sav" : "user",
                    content: item.contenu ?? "",
                    createdAt: item.date_creation
                        ? new Date(item.date_creation).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
                        : new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
                    feedback: (item.feedback === 1 || item.feedback === -1) ? item.feedback : null,
                }))
                setMessages(normalized)
            } catch (err) {
                console.error("Erreur chargement messages :", err)
            }
        }
        loadMessages()
    }, [sessionIdNumber])

    useEffect(() => {
        async function loadSessionStatus() {
            if (!Number.isFinite(sessionIdNumber)) return
            const userId = localStorage.getItem("user_id")
            if (!userId) return
            try {
                const response = await fetch(`/api/sessions?user_id=${userId}`)
                if (!response.ok) return
                const data = await response.json()
                if (!Array.isArray(data)) return
                const currentSession = data.find((item: { id?: number; status?: string | null }) => item.id === sessionIdNumber)
                if (currentSession?.status === "closed") setIsClosed(true)
                if (currentSession?.status === "transferred") setIsTransferred(true)
            } catch (err) {
                console.error("Erreur chargement session :", err)
            }
        }
        loadSessionStatus()
    }, [sessionIdNumber])

    const handleTransfer = async (reason: string) => {
        setIsTransferring(true)
        try {
            const res = await fetch(`/api/sessions/${sessionIdNumber}/transfer`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reason }),
            })
            if (res.ok) {
                setIsTransferred(true)
                setShowTransferPanel(false)
                // Reload messages to show the system notification
                const msgsRes = await fetch(`/api/messages?session_id=${sessionIdNumber}`)
                if (msgsRes.ok) {
                    const data = await msgsRes.json()
                    if (Array.isArray(data)) {
                        setMessages((data as BackendChatMessage[]).map((item) => ({
                            id: String(item.id ?? makeId()),
                            role: item.type_envoyeur === "ai" ? "ai" : item.type_envoyeur === "sav" ? "sav" : "user",
                            content: item.contenu ?? "",
                            createdAt: item.date_creation
                                ? new Date(item.date_creation).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
                                : new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
                            feedback: null,
                        })))
                    }
                }
            }
        } catch {
            setError("Impossible de contacter le serveur.")
        } finally {
            setIsTransferring(false)
        }
    }

    const handleFeedback = async (messageId: string, value: 1 | -1) => {
        setMessages(prev =>
            prev.map(m => m.id === messageId ? { ...m, feedback: value } : m)
        )
        try {
            await fetch(`/api/messages/${messageId}/feedback`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ feedback: value }),
            })
        } catch {
            setMessages(prev =>
                prev.map(m => m.id === messageId ? { ...m, feedback: null } : m)
            )
        }
    }

    const handleSend = async (event?: React.FormEvent, customPrompt?: string) => {
        event?.preventDefault()
        setError(null)
        const trimmed = (customPrompt ?? input).trim()
        if (!trimmed || isSending) return
        if (isClosed) {
            setError("Cette conversation est clôturée. Vous ne pouvez plus envoyer de message.")
            return
        }

        const userMessage: ChatMessage = {
            id: makeId(),
            role: "user",
            content: trimmed,
            createdAt: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
        }
        setMessages(prev => [...prev, userMessage])
        setInput("")

        if (!aiEnabled || isTransferred) {
            try {
                if (!Number.isFinite(sessionIdNumber)) { setError("Session invalide."); return }
                const response = await fetch("/api/messages", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id_session: sessionIdNumber, type_envoyeur: "user", contenu: trimmed })
                })
                if (!response.ok) {
                    if (response.status === 401) {
                        setMessages(prev => prev.filter(m => m.id !== userMessage.id))
                        setError("Session expirée. Veuillez vous reconnecter.")
                        return
                    }
                    const data = await response.json()
                    setMessages(prev => prev.filter(m => m.id !== userMessage.id))
                    if (response.status === 400 && data?.detail === "Cette conversation est clôturée.") setIsClosed(true)
                    setError(data?.detail || "Erreur lors de l'enregistrement du message.")
                }
            } catch {
                setMessages(prev => prev.filter(m => m.id !== userMessage.id))
                setError("Impossible de contacter le serveur.")
            }
            return
        }

        setIsSending(true)
        const streamId = makeId()
        const now = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
        setMessages(prev => [...prev, { id: streamId, role: "ai", content: "", createdAt: now, feedback: null }])

        try {
            if (!Number.isFinite(sessionIdNumber)) { setError("Session invalide."); setIsSending(false); return }
            const response = await fetch(
                `/api/ask?question=${encodeURIComponent(trimmed)}&session_id=${sessionIdNumber}&mode=rag_llm`,
                { method: "POST", credentials: "include" }
            )
            if (!response.ok || !response.body) {
                const data = await response.json().catch(() => null)
                setMessages(prev => prev.filter(m => m.id !== userMessage.id && m.id !== streamId))
                if (response.status === 400 && data?.detail === "Cette conversation est clôturée.") setIsClosed(true)
                setError(data?.detail || "Erreur de l'assistant IA.")
                setIsSending(false)
                return
            }
            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let accumulated = ""
            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                accumulated += decoder.decode(value, { stream: true })
                setMessages(prev => prev.map(m => m.id === streamId ? { ...m, content: accumulated } : m))
            }
        } catch {
            setMessages(prev => prev.filter(m => m.id !== userMessage.id && m.id !== streamId))
            setError("Erreur de connexion au serveur.")
        } finally {
            setIsSending(false)
        }
    }

    const isLastMessage = (id: string) => messages[messages.length - 1]?.id === id

    return (
        <div className="flex flex-col h-full bg-slate-50/30">
            <header className="h-16 border-b bg-white flex items-center justify-between px-6 shrink-0 shadow-sm">
                <div className="flex items-center gap-3">
                    <Avatar className="h-10 w-10 border-2 border-primary/10">
                        <AvatarFallback className="bg-primary/5 text-primary text-xs font-bold">{username.slice(0, 2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div>
                        <h2 className="font-bold text-sm text-slate-800">{username} <span className="text-slate-400 font-normal ml-1">#S{sessionId}</span></h2>
                        <p className={`text-[11px] font-medium flex items-center gap-1 ${isClosed ? "text-slate-400" : isTransferred ? "text-amber-600" : "text-green-600"}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${isClosed ? "bg-slate-400" : isTransferred ? "bg-amber-500 animate-pulse" : "bg-green-500 animate-pulse"}`}></span>
                            {isClosed ? "Conversation clôturée" : isTransferred ? "En attente d'un agent SAV" : "Assistant IA Actif"}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="icon" className="text-slate-400" aria-label="Rechercher dans la conversation"><Search className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" className="text-slate-400" aria-label="Plus d'options"><MoreVertical className="h-4 w-4" /></Button>
                </div>
            </header>

            <div className="flex-1 overflow-y-auto p-6" aria-live="polite" aria-busy={isSending}>
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full max-w-2xl mx-auto space-y-10">
                        <div className="text-center space-y-4">
                            <div className="bg-indigo-600 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto shadow-xl shadow-indigo-100 mb-6">
                                <Bot className="h-9 w-9 text-white" />
                            </div>
                            <h1 className="text-3xl font-black text-slate-900 tracking-tight">Prêt à booster votre SAV ?</h1>
                            <p className="text-slate-500 text-sm max-w-sm mx-auto">Choisissez une action rapide ou posez votre question ci-dessous.</p>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full px-4">
                            {SUGGESTIONS.map((s, i) => (
                                <Card
                                    key={i}
                                    onClick={() => { if (!isClosed) void handleSend(undefined, s.prompt) }}
                                    className={`p-4 border-2 transition-all group bg-white ${isClosed ? "border-slate-100 opacity-50 cursor-not-allowed" : "border-slate-100 hover:border-indigo-500 hover:shadow-lg cursor-pointer"}`}
                                >
                                    <div className="flex items-start gap-4">
                                        <div className="p-3 rounded-xl bg-slate-50 group-hover:bg-indigo-50 transition-colors">{s.icon}</div>
                                        <div>
                                            <div className="font-bold text-sm text-slate-800 group-hover:text-indigo-600 transition-colors">{s.title}</div>
                                            <div className="text-[11px] text-slate-400">{s.desc}</div>
                                        </div>
                                    </div>
                                </Card>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="space-y-6 max-w-4xl mx-auto">
                        {messages.map((m) => (
                            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                                <div className={`max-w-[80%] flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}>
                                    <div className={`rounded-2xl px-5 py-3 text-sm shadow-sm ${m.role === "user"
                                            ? "bg-indigo-600 text-white"
                                            : m.role === "sav"
                                                ? "bg-emerald-600 text-white"
                                                : "bg-white border-2 border-slate-100 text-slate-700"
                                        }`}>
                                        {m.role === "user" ? (
                                            m.content
                                        ) : m.role === "sav" ? (
                                            m.content
                                        ) : m.content ? (
                                            <Streamdown animated isAnimating={isSending && isLastMessage(m.id)}>
                                                {m.content}
                                            </Streamdown>
                                        ) : (
                                            <span className="inline-flex gap-1 items-center text-slate-400">
                                                <span className="h-1.5 w-1.5 rounded-full bg-slate-300 animate-bounce [animation-delay:0ms]" />
                                                <span className="h-1.5 w-1.5 rounded-full bg-slate-300 animate-bounce [animation-delay:150ms]" />
                                                <span className="h-1.5 w-1.5 rounded-full bg-slate-300 animate-bounce [animation-delay:300ms]" />
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2 px-2 mt-1">
                                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-tighter">
                                            {m.role === "user" ? username : m.role === "sav" ? "Agent SAV" : "Assistant IA"} • {m.createdAt}
                                        </span>
                                        {m.role === "ai" && m.content && !(isSending && isLastMessage(m.id)) && (
                                            <div className="flex items-center gap-0.5">
                                                <button
                                                    type="button"
                                                    disabled={m.feedback !== null && m.feedback !== undefined}
                                                    onClick={() => handleFeedback(m.id, 1)}
                                                    aria-label="Marquer comme bonne réponse"
                                                    className={`p-0.5 rounded transition-colors disabled:cursor-default ${m.feedback === 1 ? "text-indigo-600" : "text-slate-300 hover:text-slate-500"}`}
                                                >
                                                    <ThumbsUp className={`h-3.5 w-3.5 ${m.feedback === 1 ? "fill-indigo-600" : ""}`} />
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={m.feedback !== null && m.feedback !== undefined}
                                                    onClick={() => handleFeedback(m.id, -1)}
                                                    aria-label="Marquer comme mauvaise réponse"
                                                    className={`p-0.5 rounded transition-colors disabled:cursor-default ${m.feedback === -1 ? "text-red-500" : "text-slate-300 hover:text-slate-500"}`}
                                                >
                                                    <ThumbsDown className={`h-3.5 w-3.5 ${m.feedback === -1 ? "fill-red-500" : ""}`} />
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            <div className="bg-white border-t border-slate-100 shadow-[0_-4px_20px_rgba(0,0,0,0.03)]">
                {/* Transferred banner */}
                {isTransferred && (
                    <div className="flex items-center gap-2 px-6 py-2.5 bg-amber-50 border-b border-amber-100 text-amber-700 text-sm">
                        <Headphones className="h-4 w-4 flex-shrink-0" />
                        <span>En attente d&apos;un agent SAV — un agent humain va vous répondre prochainement.</span>
                    </div>
                )}

                {/* Transfer reason panel */}
                {showTransferPanel && (
                    <div className="px-6 py-3 border-b border-slate-100 bg-slate-50/60">
                        <div className="max-w-4xl mx-auto">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Pourquoi souhaitez-vous parler à un agent ?</span>
                                <button onClick={() => setShowTransferPanel(false)} aria-label="Fermer le panneau de transfert" className="text-slate-400 hover:text-slate-600">
                                    <X className="h-4 w-4" />
                                </button>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {TRANSFER_REASONS.map(({ key, label, color }) => (
                                    <button
                                        key={key}
                                        disabled={isTransferring}
                                        onClick={() => handleTransfer(key)}
                                        className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${color} disabled:opacity-50`}
                                    >
                                        {isTransferring ? "…" : label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                <div className="p-6">
                    <div className="max-w-4xl mx-auto space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <div className="flex items-center gap-3 bg-slate-50 px-3 py-1.5 rounded-full border border-slate-100">
                                    <Switch checked={aiEnabled} onCheckedChange={setAiEnabled} disabled={isClosed || isTransferred} className="data-[state=checked]:bg-indigo-600" />
                                    <span className="text-[11px] font-bold text-slate-500 uppercase">IA Active</span>
                                </div>
                                {!isClosed && !isTransferred && (
                                    <button
                                        onClick={() => setShowTransferPanel(v => !v)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-slate-200 bg-slate-50 text-slate-500 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700 transition-colors text-[11px] font-bold uppercase"
                                    >
                                        <Headphones className="h-3.5 w-3.5" />
                                        Agent humain
                                    </button>
                                )}
                            </div>
                            <Badge variant="outline" className="text-indigo-600 border-indigo-100 gap-1 text-[10px] py-1">
                                <Sparkles className="h-3 w-3" /> Chiffrement actif
                            </Badge>
                        </div>
                        {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
                        <form onSubmit={handleSend} className="relative group">
                            <label htmlFor="chat-input" className="sr-only">
                                {isClosed ? "Conversation clôturée" : isTransferred ? "Message à l'agent SAV" : "Question à l'assistant IA"}
                            </label>
                            <Input
                                id="chat-input"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                disabled={isClosed || isSending}
                                placeholder={
                                    isClosed
                                        ? "Cette conversation est clôturée."
                                        : isTransferred
                                            ? "Envoyez un message à l'agent SAV..."
                                            : "Posez votre question à l'assistant..."
                                }
                                className="h-14 pl-6 pr-24 rounded-2xl border-2 border-slate-100 focus-visible:ring-indigo-500 bg-slate-50/30 transition-all text-base"
                            />
                            <div className="absolute right-2 top-2 flex items-center gap-1">
                                <Button type="submit" disabled={isClosed || isSending || !input.trim()} size="sm" className="h-10 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 shadow-lg shadow-indigo-100 transition-all">
                                    <Send className="h-4 w-4 mr-2" /> {isSending ? "Calcul..." : "Envoyer"}
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    )
}
