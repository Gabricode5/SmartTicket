"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import {
    LayoutDashboard,
    BookOpen,
    BarChart2,
    Settings,
    LogOut,
    Plus,
    MessageSquare,
    Trash2
} from "lucide-react"

interface Conversation {
    id: string
    title: string
}

type UserRole = "user" | "sav" | "admin"

interface SidebarUser {
    username: string
    email: string
    initials: string
    role: UserRole
}

const DEFAULT_USER: SidebarUser = {
    username: "Utilisateur",
    email: "chargement...",
    initials: "U",
    role: "user",
}

function normalizeRole(role: string | null): UserRole {
    if (role === "admin" || role === "sav") {
        return role
    }
    return "user"
}

export function AppSidebar() {
    const pathname = usePathname()

    const [user, setUser] = useState<SidebarUser>(DEFAULT_USER)
    const [conversations, setConversations] = useState<Conversation[]>([])
    const [isLoadingConversations, setIsLoadingConversations] = useState(false)
    const canManageKnowledgeBase = user.role === "admin" || user.role === "sav"
    const canAccessConversations = user.role !== "admin"

    useEffect(() => {
        const storedUser = localStorage.getItem("username")
        const storedEmail = localStorage.getItem("user_email") || "votre@email.com"
        const storedRole = normalizeRole(localStorage.getItem("user_role"))

        if (storedUser) {
            setUser({
                username: storedUser,
                email: storedEmail,
                initials: storedUser.substring(0, 2).toUpperCase(),
                role: storedRole
            })
        }
    }, [])

    const fetchConversations = async () => {
        const userId = localStorage.getItem("user_id")
        if (!userId) return

        setIsLoadingConversations(true)
        try {
            const response = await fetch(`/api/sessions?user_id=${userId}`)
            if (response.status === 401) {
                window.location.href = "/login"
                return
            }
            if (!response.ok) return
            const data = await response.json()
            const normalized: Conversation[] = data.map((item: { id: number | string; title?: string | null }) => ({
                id: String(item.id),
                title: item.title || "Nouvelle conversation",
            }))
            setConversations(normalized)
        } catch (error) {
            console.error("Erreur réseau :", error)
        } finally {
            setIsLoadingConversations(false)
        }
    }

    useEffect(() => {
        fetchConversations()
    }, [])

    const handleCreateConversation = async () => {
        const userId = localStorage.getItem("user_id")
        if (!userId) {
            window.location.href = "/login"
            return
        }

        try {
            const response = await fetch(`/api/sessions?user_id=${userId}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                // Laisse le backend gérer le titre automatiquement.
                body: JSON.stringify({}),
            })

            if (response.status === 401) {
                window.location.href = "/login"
                return
            }
            if (!response.ok) return
            const newSession = await response.json()
            window.location.href = `/ai-assistant/${newSession.id}`
        } catch (error) {
            console.error("Erreur réseau :", error)
        }
    }

    const handleDeleteConversation = async (conversationId: string) => {
        const confirmed = window.confirm("Supprimer cette conversation ?")
        if (!confirmed) return
        try {
            const response = await fetch(`/api/sessions/${conversationId}`, {
                method: "DELETE"
            })
            if (response.status === 401) {
                window.location.href = "/login"
                return
            }

            if (!response.ok) return
            setConversations((prev) => prev.filter((chat) => chat.id !== conversationId))

            if (pathname === `/ai-assistant/${conversationId}`) {
                window.location.href = "/"
            }
        } catch (error) {
            console.error("Erreur réseau :", error)
        }
    }

    const isActive = (path: string) => {
        if (path === "/") return pathname === "/"
        return pathname?.startsWith(path)
    }

    const handleLogout = async () => {
        try {
            await fetch("/api/logout", { method: "POST" })
        } catch {
            // continue
        }
        localStorage.removeItem("username")
        localStorage.removeItem("user_email")
        localStorage.removeItem("user_role")
        localStorage.removeItem("user_id")
        window.location.href = "/login"
    }

    return (
        <aside className="w-64 bg-sidebar text-sidebar-foreground border-r border-sidebar-border hidden md:flex flex-col h-full">
            {/* Logo Area */}
            <div className="h-16 flex items-center px-6 border-b border-sidebar-border">
                <div className="flex items-center gap-2 font-bold text-xl">
                    <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground">
                        A
                    </div>
                    <span>SmartTicket</span>
                </div>
            </div>

            {/* Navigation & Historique */}
            <div className="flex-1 overflow-y-auto py-6 px-3 flex flex-col gap-6">
                
                {/* 1. Menu Principal */}
                <div>
                    <h3 className="px-4 text-xs font-semibold text-sidebar-foreground/50 uppercase tracking-wider mb-2">
                        Menu Principal
                    </h3>
                    <div className="space-y-1">
                        <Button
                            variant={isActive("/") ? "secondary" : "ghost"}
                            asChild
                            className={cn("w-full justify-start", isActive("/") && "bg-sidebar-accent")}
                        >
                            <Link href="/">
                                <LayoutDashboard className="mr-3 h-4 w-4" />
                                Tableau de bord
                            </Link>
                        </Button>

                        {canManageKnowledgeBase && (
                            <Button
                                variant={isActive("/knowledge-base") ? "secondary" : "ghost"}
                                asChild
                                className={cn("w-full justify-start", isActive("/knowledge-base") && "bg-sidebar-accent")}
                            >
                                <Link href="/knowledge-base">
                                    <BookOpen className="mr-3 h-4 w-4" />
                                    Base de connaissances
                                </Link>
                            </Button>
                        )}
                    </div>
                </div>

                {/* 2. Section Discussions (Style ChatGPT) */}
                {canAccessConversations && (
                <div>
                    <div className="flex items-center justify-between px-4 mb-2">
                        <h3 className="text-xs font-semibold text-sidebar-foreground/50 uppercase tracking-wider">
                            Discussions
                        </h3>
                        <button
                            type="button"
                            onClick={handleCreateConversation}
                            className="hover:text-primary transition-colors"
                            title="Nouvelle discussion"
                        >
                            <Plus className="h-4 w-4 cursor-pointer" />
                        </button>
                    </div>
                    
                    <div className="space-y-1">
                        {/* Bouton pour créer une nouvelle discussion */}
                        <Button
                            variant="outline"
                            className="w-full justify-start border-dashed border-sidebar-border hover:border-primary/50 mb-2"
                            onClick={handleCreateConversation}
                        >
                            <Plus className="mr-2 h-4 w-4" />
                            Nouveau chat
                        </Button>

                        {/* Liste des conversations récentes */}
                        <div className="max-h-[300px] overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                            {isLoadingConversations ? (
                                <div className="px-3 text-xs text-sidebar-foreground/60">
                                    Chargement des conversations...
                                </div>
                            ) : conversations.length === 0 ? (
                                <div className="px-3 text-xs text-sidebar-foreground/60">
                                    Aucune conversation pour le moment.
                                </div>
                            ) : (
                                conversations.map((chat) => (
                                    <div
                                        key={chat.id}
                                        className={cn(
                                            "group flex items-center w-full rounded-md px-3 h-9 text-sm",
                                            pathname === `/ai-assistant/${chat.id}`
                                                ? "bg-sidebar-accent"
                                                : "hover:bg-sidebar-accent/60"
                                        )}
                                    >
                                        <Link
                                            href={`/ai-assistant/${chat.id}`}
                                            className="flex items-center gap-3 flex-1 min-w-0"
                                        >
                                            <MessageSquare className="h-3.5 w-3.5 flex-shrink-0" />
                                            <span className="truncate">{chat.title}</span>
                                        </Link>
                                        <button
                                            type="button"
                                            onClick={() => handleDeleteConversation(chat.id)}
                                            className="ml-2 rounded-md p-1 text-sidebar-foreground/40 hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition"
                                            title="Supprimer"
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
                )}

                {user.role === "admin" && (
                    <div>
                        <h3 className="px-4 text-xs font-semibold text-sidebar-foreground/50 uppercase tracking-wider mb-2">
                            Outils IA
                        </h3>
                        <div className="space-y-1">
                            <Button
                                variant={isActive("/analytics") ? "secondary" : "ghost"}
                                asChild
                                className={cn("w-full justify-start", isActive("/analytics") && "bg-sidebar-accent")}
                            >
                                <Link href="/analytics">
                                    <BarChart2 className="mr-3 h-4 w-4" />
                                    Analytique
                                </Link>
                            </Button>
                        </div>
                    </div>
                )}
            </div>

            {/* User Footer */}
            <div className="p-4 border-t border-sidebar-border">
                <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-sidebar-accent cursor-default group transition-all">
                    <Avatar className="h-9 w-9 border border-sidebar-border">
                        <AvatarFallback className="bg-primary/10 text-primary text-xs font-bold">
                            {user.initials}
                        </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 overflow-hidden">
                        <p className="text-sm font-semibold leading-none truncate text-sidebar-foreground flex items-center gap-2">
                            {user.username}
                            {user.role === "admin" && <span className="text-[10px] bg-amber-100 text-amber-700 px-1 rounded">Pro</span>}
                        </p>
                        <p className="text-[11px] text-sidebar-foreground/60 truncate mt-1">
                            {user.email}
                        </p>
                    </div>
                    <div className="flex items-center gap-1">
                        <Link
                            href="/settings"
                            className={cn(
                                "p-1.5 rounded-md text-sidebar-foreground/40 hover:text-primary hover:bg-primary/10 transition-all",
                                isActive("/settings") && "text-primary bg-primary/10"
                            )}
                            title="Modifier mon compte"
                        >
                            <Settings className="h-4 w-4" />
                        </Link>
                        <button
                            onClick={handleLogout}
                            className="p-1.5 rounded-md text-sidebar-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-all"
                            title="Se déconnecter"
                        >
                            <LogOut className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </div>
        </aside>
    )
}
