"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    Users, Shield, Headphones, Crown, MessageCircle, UserCog, TrendingUp,
    ChevronRight, ChevronLeft, UserCheck, UserX, Pencil, Trash2, AlertCircle, CircleDot,
    CheckCircle2, BarChart2, BookOpen, ArrowRight,
} from "lucide-react"
import Link from "next/link"
import { REASON_LABELS, REASON_STYLES, type SessionItem, type SessionSearchResult, type TransferredSession, type UserItem } from "./types"
import { renderSnippet } from "./searchSnippet"

export default function AdminDashboard({ currentUserId }: { currentUserId: number }) {
    const [users, setUsers] = useState<UserItem[]>([])
    const [savUsers, setSavUsers] = useState<UserItem[]>([])
    const [adminUsers, setAdminUsers] = useState<UserItem[]>([])
    const [selectedUser, setSelectedUser] = useState<UserItem | null>(null)
    const [sessions, setSessions] = useState<SessionItem[]>([])
    const [selectedSession, setSelectedSession] = useState<SessionItem | null>(null)
    const [transferredSessions, setTransferredSessions] = useState<TransferredSession[]>([])
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [closingSessionId, setClosingSessionId] = useState<number | null>(null)
    const [updatingRoleUserId, setUpdatingRoleUserId] = useState<number | null>(null)
    const [updatingUserId, setUpdatingUserId] = useState<number | null>(null)
    const [editDialogOpen, setEditDialogOpen] = useState(false)
    const [editingUser, setEditingUser] = useState<UserItem | null>(null)
    const [editForm, setEditForm] = useState({ username: "", email: "", prenom: "", nom: "", role: "" })
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
    const [deletingUser, setDeletingUser] = useState<UserItem | null>(null)
    const [sessionQuery, setSessionQuery] = useState("")
    const [sessionSearchResults, setSessionSearchResults] = useState<SessionSearchResult[] | null>(null)
    const [isSearchingSessions, setIsSearchingSessions] = useState(false)

    const PAGE_SIZE = 8
    const [usersPage, setUsersPage] = useState(1)
    const [savPage, setSavPage] = useState(1)
    const [adminPage, setAdminPage] = useState(1)
    const [sessionsPage, setSessionsPage] = useState(1)
    const [transfersPage, setTransfersPage] = useState(1)

    useEffect(() => {
        loadAll()
    }, [])

    // Full-text search (débounced) sur le contenu des messages + titres de l'utilisateur sélectionné.
    useEffect(() => {
        const trimmed = sessionQuery.trim()
        if (!selectedUser || !trimmed) {
            setSessionSearchResults(null)
            setIsSearchingSessions(false)
            return
        }
        setIsSearchingSessions(true)
        const timeoutId = setTimeout(async () => {
            try {
                const res = await fetch(`/api/sessions/search?user_id=${selectedUser.id}&q=${encodeURIComponent(trimmed)}`)
                setSessionSearchResults(res.ok ? await res.json() : [])
            } catch {
                setSessionSearchResults([])
            } finally {
                setIsSearchingSessions(false)
            }
        }, 300)
        return () => clearTimeout(timeoutId)
    }, [sessionQuery, selectedUser])

    const loadAll = async () => {
        setIsLoading(true)
        setError(null)
        try {
            const [usersRes, savRes, adminsRes, transferRes] = await Promise.all([
                fetch("/api/users?role=user"),
                fetch("/api/users?role=sav"),
                fetch("/api/users?role=admin"),
                fetch("/api/sessions/transferred"),
            ])
            if ([usersRes, savRes, adminsRes].some((r) => r.status === 401)) {
                setError("Session expirée. Veuillez vous reconnecter.")
                return
            }
            if (!usersRes.ok || !savRes.ok || !adminsRes.ok) {
                setError("Impossible de charger les utilisateurs.")
                return
            }
            setUsers(await usersRes.json())
            setSavUsers(await savRes.json())
            setAdminUsers(await adminsRes.json())
            if (transferRes.ok) setTransferredSessions(await transferRes.json())
        } catch {
            setError("Erreur réseau.")
        } finally {
            setIsLoading(false)
        }
    }

    const handleSelectUser = async (u: UserItem) => {
        setSelectedUser(u)
        setSelectedSession(null)
        setSessionsPage(1)
        setSessionQuery("")
        setSessionSearchResults(null)
        setError(null)
        try {
            const res = await fetch(`/api/sessions?user_id=${u.id}`)
            if (res.status === 401) { setError("Session expirée."); return }
            if (!res.ok) { setError("Impossible de charger les sessions."); return }
            setSessions(await res.json())
        } catch {
            setError("Erreur réseau.")
        }
    }

    const handleChangeRole = async (u: UserItem, newRole: "user" | "sav" | "admin") => {
        setError(null)
        setUpdatingRoleUserId(u.id)
        try {
            const res = await fetch(`/api/users/${u.id}/role`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ role: newRole }),
            })
            const data = await res.json()
            if (!res.ok) {
                setError(res.status === 401 ? "Session expirée." : data?.detail || "Impossible de modifier le rôle.")
                return
            }
            if (selectedUser?.id === u.id) setSelectedUser((prev) => prev ? { ...prev, role: data.role } : prev)
            await loadAll()
        } catch {
            setError("Erreur réseau.")
        } finally {
            setUpdatingRoleUserId(null)
        }
    }

    const handleEditUser = (u: UserItem) => {
        setEditingUser(u)
        setEditForm({ username: u.username, email: u.email, prenom: u.prenom || "", nom: u.nom || "", role: u.role })
        setEditDialogOpen(true)
    }

    const handleEditSubmit = async () => {
        if (!editingUser) return
        setError(null)
        setUpdatingUserId(editingUser.id)
        try {
            const res = await fetch(`/api/users/${editingUser.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: editForm.username.trim(),
                    email: editForm.email.trim().toLowerCase(),
                    prenom: editForm.prenom.trim(),
                    nom: editForm.nom.trim(),
                    role: editForm.role.trim().toLowerCase(),
                }),
            })
            const data = await res.json()
            if (!res.ok) {
                setError(res.status === 401 ? "Session expirée." : data?.detail || "Impossible de modifier l'utilisateur.")
                return
            }
            if (selectedUser?.id === editingUser.id) setSelectedUser(data)
            setEditDialogOpen(false)
            await loadAll()
        } catch {
            setError("Erreur réseau.")
        } finally {
            setUpdatingUserId(null)
        }
    }

    const handleDeleteUser = (u: UserItem) => {
        setDeletingUser(u)
        setDeleteDialogOpen(true)
    }

    const handleDeleteConfirm = async () => {
        if (!deletingUser) return
        const u = deletingUser
        setDeleteDialogOpen(false)
        setError(null)
        setUpdatingUserId(u.id)
        try {
            const res = await fetch(`/api/users/${u.id}`, { method: "DELETE" })
            if (!res.ok) {
                const data = await res.json()
                setError(res.status === 401 ? "Session expirée." : data?.detail || "Impossible de supprimer l'utilisateur.")
                return
            }
            if (selectedUser?.id === u.id) { setSelectedUser(null); setSelectedSession(null); setSessions([]) }
            await loadAll()
        } catch {
            setError("Erreur réseau.")
        } finally {
            setUpdatingUserId(null)
        }
    }

    const handleCloseSession = async (s: SessionItem) => {
        if (!window.confirm(`Clôturer la session #${s.id} ?`)) return
        setClosingSessionId(s.id)
        try {
            const res = await fetch(`/api/sessions/${s.id}/close`, { method: "POST" })
            if (!res.ok) {
                const data = await res.json()
                setError(data?.detail || "Impossible de clôturer la session.")
                return
            }
            if (selectedUser) await handleSelectUser(selectedUser)
        } catch {
            setError("Erreur réseau.")
        } finally {
            setClosingSessionId(null)
        }
    }

    const userColumnClass = (selected: boolean, color: string) =>
        `px-4 py-3 transition-colors ${selected ? `bg-${color}-50/60` : "hover:bg-slate-50/80"}`

    return (
        <>
            <div className="flex flex-col min-h-full bg-slate-50/50">
                <header className="flex items-center justify-between px-8 py-5 bg-white border-b sticky top-0 z-10 shadow-sm">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-600 shadow-sm">
                            <UserCog className="h-5 w-5 text-white" />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold tracking-tight text-slate-900">Espace Admin</h1>
                            <p className="text-xs text-slate-500">Gestion des utilisateurs &amp; conversations</p>
                        </div>
                        <Badge className="bg-indigo-50 text-indigo-700 hover:bg-indigo-50 border border-indigo-200 gap-1 ml-2">
                            <Shield className="h-3 w-3" /> Administrateur
                        </Badge>
                    </div>
                    <div className="flex items-center gap-1.5 bg-white border rounded-lg px-3 py-1.5 shadow-sm text-sm">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="font-medium text-slate-700">{users.length + savUsers.length + adminUsers.length}</span>
                        <span className="text-slate-500">utilisateurs</span>
                    </div>
                </header>

                <div className="p-8 space-y-6 max-w-7xl mx-auto w-full">
                    {error && (
                        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                            {error}
                        </div>
                    )}

                    <div className="grid gap-5 lg:grid-cols-4">
                        {/* Utilisateurs */}
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                                        <Users className="h-4 w-4 text-blue-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-slate-800">Utilisateurs</p>
                                        <p className="text-xs text-slate-400">Comptes clients</p>
                                    </div>
                                </div>
                                <Badge className="bg-blue-50 text-blue-600 border-blue-100 text-xs font-semibold">{users.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {isLoading ? (
                                    <div className="px-5 py-8 text-center text-sm text-slate-400">Chargement...</div>
                                ) : users.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-slate-400">Aucun utilisateur</div>
                                ) : users.slice((usersPage - 1) * PAGE_SIZE, usersPage * PAGE_SIZE).map((u) => (
                                    <div key={u.id} className={userColumnClass(selectedUser?.id === u.id, "blue")}>
                                        <button onClick={() => handleSelectUser(u)} className="w-full text-left flex items-center gap-3 mb-2.5">
                                            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                                                <span className="text-xs font-bold text-blue-600">{u.username.charAt(0).toUpperCase()}</span>
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-slate-800 truncate">{u.username}</div>
                                                <div className="text-xs text-slate-400 truncate">{u.email}</div>
                                            </div>
                                            {selectedUser?.id === u.id && <ChevronRight className="h-4 w-4 text-blue-400 ml-auto flex-shrink-0" />}
                                        </button>
                                        <div className="flex items-center gap-1.5 pl-11">
                                            <button onClick={() => handleChangeRole(u, "sav")} disabled={updatingRoleUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors disabled:opacity-50">
                                                <UserCheck className="h-3 w-3" />
                                                {updatingRoleUserId === u.id ? "..." : "SAV"}
                                            </button>
                                            <button onClick={() => handleEditUser(u)} disabled={updatingUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200 transition-colors disabled:opacity-50">
                                                <Pencil className="h-3 w-3" />
                                            </button>
                                            <button onClick={() => handleDeleteUser(u)} disabled={updatingUserId === u.id || currentUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-red-50 text-red-500 hover:bg-red-100 border border-red-200 transition-colors disabled:opacity-50">
                                                <Trash2 className="h-3 w-3" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {Math.ceil(users.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100">
                                    <button onClick={() => setUsersPage(p => p - 1)} disabled={usersPage <= 1} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-slate-400">{usersPage} / {Math.ceil(users.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setUsersPage(p => p + 1)} disabled={usersPage >= Math.ceil(users.length / PAGE_SIZE)} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Agents SAV */}
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
                                        <Headphones className="h-4 w-4 text-emerald-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-slate-800">Agents SAV</p>
                                        <p className="text-xs text-slate-400">Support client</p>
                                    </div>
                                </div>
                                <Badge className="bg-emerald-50 text-emerald-600 border-emerald-100 text-xs font-semibold">{savUsers.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {isLoading ? (
                                    <div className="px-5 py-8 text-center text-sm text-slate-400">Chargement...</div>
                                ) : savUsers.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-slate-400">Aucun agent SAV</div>
                                ) : savUsers.slice((savPage - 1) * PAGE_SIZE, savPage * PAGE_SIZE).map((u) => (
                                    <div key={u.id} className={userColumnClass(selectedUser?.id === u.id, "emerald")}>
                                        <button onClick={() => handleSelectUser(u)} className="w-full text-left flex items-center gap-3 mb-2.5">
                                            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                                                <span className="text-xs font-bold text-emerald-600">{u.username.charAt(0).toUpperCase()}</span>
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-slate-800 truncate">{u.username}</div>
                                                <div className="text-xs text-slate-400 truncate">{u.email}</div>
                                            </div>
                                            {selectedUser?.id === u.id && <ChevronRight className="h-4 w-4 text-emerald-400 ml-auto flex-shrink-0" />}
                                        </button>
                                        <div className="flex items-center gap-1.5 pl-11">
                                            <button onClick={() => handleChangeRole(u, "user")} disabled={updatingRoleUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-orange-50 text-orange-600 hover:bg-orange-100 border border-orange-200 transition-colors disabled:opacity-50">
                                                <UserX className="h-3 w-3" />
                                                {updatingRoleUserId === u.id ? "..." : "Retirer"}
                                            </button>
                                            <button onClick={() => handleEditUser(u)} disabled={updatingUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200 transition-colors disabled:opacity-50">
                                                <Pencil className="h-3 w-3" />
                                            </button>
                                            <button onClick={() => handleDeleteUser(u)} disabled={updatingUserId === u.id || currentUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-red-50 text-red-500 hover:bg-red-100 border border-red-200 transition-colors disabled:opacity-50">
                                                <Trash2 className="h-3 w-3" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {Math.ceil(savUsers.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100">
                                    <button onClick={() => setSavPage(p => p - 1)} disabled={savPage <= 1} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-slate-400">{savPage} / {Math.ceil(savUsers.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setSavPage(p => p + 1)} disabled={savPage >= Math.ceil(savUsers.length / PAGE_SIZE)} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Admins */}
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
                                        <Crown className="h-4 w-4 text-indigo-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-slate-800">Admins</p>
                                        <p className="text-xs text-slate-400">Administrateurs</p>
                                    </div>
                                </div>
                                <Badge className="bg-indigo-50 text-indigo-600 border-indigo-100 text-xs font-semibold">{adminUsers.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {isLoading ? (
                                    <div className="px-5 py-8 text-center text-sm text-slate-400">Chargement...</div>
                                ) : adminUsers.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-slate-400">Aucun admin</div>
                                ) : adminUsers.slice((adminPage - 1) * PAGE_SIZE, adminPage * PAGE_SIZE).map((u) => (
                                    <div key={u.id} className={userColumnClass(selectedUser?.id === u.id, "indigo")}>
                                        <button onClick={() => handleSelectUser(u)} className="w-full text-left flex items-center gap-3 mb-2.5">
                                            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                                                <span className="text-xs font-bold text-indigo-600">{u.username.charAt(0).toUpperCase()}</span>
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-slate-800 truncate">{u.username}</div>
                                                <div className="text-xs text-slate-400 truncate">{u.email}</div>
                                            </div>
                                            {selectedUser?.id === u.id && <ChevronRight className="h-4 w-4 text-indigo-400 ml-auto flex-shrink-0" />}
                                        </button>
                                        <div className="flex items-center gap-1.5 pl-11">
                                            <button onClick={() => handleEditUser(u)} disabled={updatingUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200 transition-colors disabled:opacity-50">
                                                <Pencil className="h-3 w-3" /> Modifier
                                            </button>
                                            <button onClick={() => handleDeleteUser(u)} disabled={updatingUserId === u.id || currentUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-red-50 text-red-500 hover:bg-red-100 border border-red-200 transition-colors disabled:opacity-50">
                                                <Trash2 className="h-3 w-3" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {Math.ceil(adminUsers.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100">
                                    <button onClick={() => setAdminPage(p => p - 1)} disabled={adminPage <= 1} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-slate-400">{adminPage} / {Math.ceil(adminUsers.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setAdminPage(p => p + 1)} disabled={adminPage >= Math.ceil(adminUsers.length / PAGE_SIZE)} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Conversations */}
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-violet-50 flex items-center justify-center">
                                        <MessageCircle className="h-4 w-4 text-violet-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-slate-800">Conversations</p>
                                        <p className="text-xs text-slate-400">{selectedUser ? selectedUser.username : "Sélectionner"}</p>
                                    </div>
                                </div>
                                {sessions.length > 0 && (
                                    <Badge className="bg-violet-50 text-violet-600 border-violet-100 text-xs font-semibold">{sessions.length}</Badge>
                                )}
                            </div>
                            {selectedUser && (
                                <div className="px-4 py-2.5 border-b border-slate-100">
                                    <Input
                                        value={sessionQuery}
                                        onChange={(e) => setSessionQuery(e.target.value)}
                                        placeholder="Rechercher dans les conversations..."
                                        className="h-8 text-sm"
                                    />
                                </div>
                            )}
                            <div className="divide-y divide-slate-50">
                                {!selectedUser ? (
                                    <div className="px-5 py-10 text-center">
                                        <MessageCircle className="h-8 w-8 text-slate-200 mx-auto mb-2" />
                                        <p className="text-sm text-slate-400">Sélectionne un utilisateur</p>
                                    </div>
                                ) : sessionQuery.trim() ? (
                                    isSearchingSessions ? (
                                        <div className="px-5 py-8 text-center text-sm text-slate-400">Recherche...</div>
                                    ) : !sessionSearchResults || sessionSearchResults.length === 0 ? (
                                        <div className="px-5 py-8 text-center text-sm text-slate-400">Aucun résultat pour « {sessionQuery.trim()} »</div>
                                    ) : (
                                        sessionSearchResults.map((s) => (
                                            <div
                                                key={s.id}
                                                role="button"
                                                tabIndex={0}
                                                onClick={() => setSelectedSession(s)}
                                                onKeyDown={(e) => {
                                                    if (e.key === "Enter" || e.key === " ") {
                                                        e.preventDefault()
                                                        setSelectedSession(s)
                                                    }
                                                }}
                                                className={`w-full text-left px-4 py-3 transition-colors cursor-pointer ${selectedSession?.id === s.id ? "bg-violet-50/70" : "hover:bg-slate-50/80"}`}
                                            >
                                                <div className="flex items-start justify-between gap-2">
                                                    <div className="min-w-0">
                                                        <div className="text-sm font-medium text-slate-800 truncate">{s.title || "Sans titre"}</div>
                                                        {s.snippet ? (
                                                            <div className="text-xs text-slate-400 mt-0.5 line-clamp-2">{renderSnippet(s.snippet)}</div>
                                                        ) : (
                                                            <div className="text-xs text-slate-400 mt-0.5">#{s.id}</div>
                                                        )}
                                                    </div>
                                                    <div className={`flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full flex-shrink-0 ${s.status === "closed" ? "bg-slate-100 text-slate-500" : s.status === "transferred" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                                                        {s.status === "closed" ? <><CheckCircle2 className="h-2.5 w-2.5" /> Clôturée</>
                                                            : s.status === "transferred" ? <><AlertCircle className="h-2.5 w-2.5" /> Transférée</>
                                                            : <><CircleDot className="h-2.5 w-2.5" /> Ouverte</>}
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    )
                                ) : sessions.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-slate-400">Aucune session</div>
                                ) : sessions.slice((sessionsPage - 1) * PAGE_SIZE, sessionsPage * PAGE_SIZE).map((s) => (
                                    <div
                                        key={s.id}
                                        role="button"
                                        tabIndex={0}
                                        onClick={() => setSelectedSession(s)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" || e.key === " ") {
                                                e.preventDefault()
                                                setSelectedSession(s)
                                            }
                                        }}
                                        className={`w-full text-left px-4 py-3 transition-colors cursor-pointer ${selectedSession?.id === s.id ? "bg-violet-50/70" : "hover:bg-slate-50/80"}`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-slate-800 truncate">{s.title || "Sans titre"}</div>
                                                <div className="text-xs text-slate-400 mt-0.5">#{s.id}</div>
                                            </div>
                                            <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                                                <div className={`flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full ${s.status === "closed" ? "bg-slate-100 text-slate-500" : s.status === "transferred" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                                                    {s.status === "closed" ? <><CheckCircle2 className="h-2.5 w-2.5" /> Clôturée</>
                                                        : s.status === "transferred" ? <><AlertCircle className="h-2.5 w-2.5" /> Transférée</>
                                                        : <><CircleDot className="h-2.5 w-2.5" /> Ouverte</>}
                                                </div>
                                                {s.status !== "closed" && (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); handleCloseSession(s) }}
                                                        disabled={closingSessionId === s.id}
                                                        className="text-[11px] px-2 py-0.5 rounded-md bg-slate-50 text-slate-500 hover:bg-slate-100 border border-slate-200 transition-colors disabled:opacity-50"
                                                    >
                                                        {closingSessionId === s.id ? "..." : "Clôturer"}
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {!sessionQuery.trim() && Math.ceil(sessions.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100">
                                    <button onClick={() => setSessionsPage(p => p - 1)} disabled={sessionsPage <= 1} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-slate-400">{sessionsPage} / {Math.ceil(sessions.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setSessionsPage(p => p + 1)} disabled={sessionsPage >= Math.ceil(sessions.length / PAGE_SIZE)} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Platform Overview */}
                    <div className="grid gap-5 lg:grid-cols-3">
                        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
                                        <Headphones className="h-4 w-4 text-amber-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-slate-800">Transferts en cours</p>
                                        <p className="text-xs text-slate-400">Sessions en attente d&apos;un agent SAV</p>
                                    </div>
                                </div>
                                <Badge className="bg-amber-50 text-amber-600 border-amber-100 text-xs font-semibold">{transferredSessions.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {transferredSessions.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center py-12 gap-2">
                                        <CheckCircle2 className="h-8 w-8 text-emerald-200" />
                                        <p className="text-sm text-slate-400">Aucun transfert en attente</p>
                                        <p className="text-xs text-slate-300">Tout est sous contrôle</p>
                                    </div>
                                ) : transferredSessions.slice((transfersPage - 1) * PAGE_SIZE, transfersPage * PAGE_SIZE).map((s) => (
                                    <div key={s.id} className="px-5 py-3 flex items-center gap-3">
                                        <div className="w-9 h-9 rounded-full bg-indigo-50 flex items-center justify-center flex-shrink-0 text-xs font-bold text-indigo-600 border-2 border-indigo-100">
                                            {s.username.charAt(0).toUpperCase()}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <div className="text-sm font-medium text-slate-800">{s.username}</div>
                                            <div className="text-xs text-slate-400 truncate">{s.title || "Sans titre"}</div>
                                        </div>
                                        {s.transfer_reason && (
                                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${REASON_STYLES[s.transfer_reason] ?? "bg-slate-100 text-slate-600 border-slate-200"}`}>
                                                {REASON_LABELS[s.transfer_reason] ?? s.transfer_reason}
                                            </span>
                                        )}
                                        <span className="text-xs text-slate-400 flex-shrink-0">#{s.id}</span>
                                    </div>
                                ))}
                            </div>
                            {Math.ceil(transferredSessions.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100">
                                    <button onClick={() => setTransfersPage(p => p - 1)} disabled={transfersPage <= 1} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-slate-400">{transfersPage} / {Math.ceil(transferredSessions.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setTransfersPage(p => p + 1)} disabled={transfersPage >= Math.ceil(transferredSessions.length / PAGE_SIZE)} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        <div className="space-y-5">
                            <Link href="/analytics" className="block group">
                                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 hover:border-indigo-200 hover:shadow-md transition-all">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center group-hover:bg-indigo-100 transition-colors">
                                            <BarChart2 className="h-5 w-5 text-indigo-600" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-slate-800">Analytique</p>
                                            <p className="text-xs text-slate-400">Performance IA &amp; métriques</p>
                                        </div>
                                        <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-indigo-500 transition-colors" />
                                    </div>
                                </div>
                            </Link>
                            <Link href="/knowledge-base" className="block group">
                                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 hover:border-emerald-200 hover:shadow-md transition-all">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center group-hover:bg-emerald-100 transition-colors">
                                            <BookOpen className="h-5 w-5 text-emerald-600" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-slate-800">Base de connaissances</p>
                                            <p className="text-xs text-slate-400">Gérer les sources IA</p>
                                        </div>
                                        <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-emerald-500 transition-colors" />
                                    </div>
                                </div>
                            </Link>
                            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center">
                                        <TrendingUp className="h-5 w-5 text-violet-600" />
                                    </div>
                                    <p className="text-sm font-semibold text-slate-800">Résumé</p>
                                </div>
                                <div className="space-y-2.5">
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-slate-500">Clients</span>
                                        <span className="font-semibold text-slate-700">{users.length}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-slate-500">Agents SAV</span>
                                        <span className="font-semibold text-slate-700">{savUsers.length}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-slate-500">Transferts en attente</span>
                                        <span className="font-semibold text-amber-600">{transferredSessions.length}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Edit Dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Modifier l&apos;utilisateur</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <Label htmlFor="edit-prenom">Prénom</Label>
                                <Input id="edit-prenom" value={editForm.prenom} onChange={(e) => setEditForm((f) => ({ ...f, prenom: e.target.value }))} placeholder="Prénom" />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="edit-nom">Nom</Label>
                                <Input id="edit-nom" value={editForm.nom} onChange={(e) => setEditForm((f) => ({ ...f, nom: e.target.value }))} placeholder="Nom" />
                            </div>
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="edit-username">Nom d&apos;utilisateur</Label>
                            <Input id="edit-username" value={editForm.username} onChange={(e) => setEditForm((f) => ({ ...f, username: e.target.value }))} placeholder="username" />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="edit-email">Email</Label>
                            <Input id="edit-email" type="email" value={editForm.email} onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))} placeholder="email@exemple.com" />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="edit-role">Rôle</Label>
                            <Select value={editForm.role} onValueChange={(v) => setEditForm((f) => ({ ...f, role: v }))}>
                                <SelectTrigger id="edit-role"><SelectValue placeholder="Choisir un rôle" /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="user">Utilisateur</SelectItem>
                                    <SelectItem value="sav">Agent SAV</SelectItem>
                                    <SelectItem value="admin">Administrateur</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter className="gap-2">
                        <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Annuler</Button>
                        <Button onClick={handleEditSubmit} disabled={updatingUserId === editingUser?.id || !editForm.username.trim() || !editForm.email.trim()} className="bg-indigo-600 hover:bg-indigo-700 text-white">
                            {updatingUserId === editingUser?.id ? "Enregistrement..." : "Enregistrer"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Dialog */}
            <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Supprimer le compte ?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Vous êtes sur le point de supprimer le compte de{" "}
                            <span className="font-semibold text-slate-800">{deletingUser?.username}</span>{" "}
                            ({deletingUser?.email}). Cette action est irréversible.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Annuler</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDeleteConfirm} className="bg-red-600 hover:bg-red-700 text-white">
                            Supprimer
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    )
}
