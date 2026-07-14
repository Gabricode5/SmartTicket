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
import { REASON_STYLES, type SessionItem, type SessionSearchResult, type TransferredSession, type UserItem } from "./types"
import { renderSnippet } from "./searchSnippet"
import { CsvImportDialog } from "./CsvImportDialog"
import { useLocale } from "@/lib/i18n/LocaleContext"

export default function AdminDashboard({ currentUserId }: { currentUserId: number }) {
    const { messages: t } = useLocale()
    const reasonLabel = (reason: string | null | undefined) => (reason ? t.common.reasons[reason as keyof typeof t.common.reasons] ?? reason : reason)
    const [users, setUsers] = useState<UserItem[]>([])
    const [savUsers, setSavUsers] = useState<UserItem[]>([])
    const [superviseurUsers, setSuperviseurUsers] = useState<UserItem[]>([])
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
    const [superviseurPage, setSuperviseurPage] = useState(1)
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
            const [usersRes, savRes, superviseursRes, adminsRes, transferRes] = await Promise.all([
                fetch("/api/users?role=user"),
                fetch("/api/users?role=sav"),
                fetch("/api/users?role=superviseur"),
                fetch("/api/users?role=admin"),
                fetch("/api/sessions/transferred"),
            ])
            if ([usersRes, savRes, superviseursRes, adminsRes].some((r) => r.status === 401)) {
                setError(t.admin.sessionExpired)
                return
            }
            if (!usersRes.ok || !savRes.ok || !superviseursRes.ok || !adminsRes.ok) {
                setError(t.admin.loadUsersError)
                return
            }
            setUsers(await usersRes.json())
            setSavUsers(await savRes.json())
            setSuperviseurUsers(await superviseursRes.json())
            setAdminUsers(await adminsRes.json())
            if (transferRes.ok) setTransferredSessions(await transferRes.json())
        } catch {
            setError(t.admin.networkError)
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
            if (res.status === 401) { setError(t.admin.sessionExpiredShort); return }
            if (!res.ok) { setError(t.admin.loadSessionsError); return }
            setSessions(await res.json())
        } catch {
            setError(t.admin.networkError)
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
                setError(res.status === 401 ? t.admin.sessionExpiredShort : data?.detail || t.admin.roleChangeError)
                return
            }
            if (selectedUser?.id === u.id) setSelectedUser((prev) => prev ? { ...prev, role: data.role } : prev)
            await loadAll()
        } catch {
            setError(t.admin.networkError)
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
                setError(res.status === 401 ? t.admin.sessionExpiredShort : data?.detail || t.admin.editUserError)
                return
            }
            if (selectedUser?.id === editingUser.id) setSelectedUser(data)
            setEditDialogOpen(false)
            await loadAll()
        } catch {
            setError(t.admin.networkError)
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
                setError(res.status === 401 ? t.admin.sessionExpiredShort : data?.detail || t.admin.deleteUserError)
                return
            }
            if (selectedUser?.id === u.id) { setSelectedUser(null); setSelectedSession(null); setSessions([]) }
            await loadAll()
        } catch {
            setError(t.admin.networkError)
        } finally {
            setUpdatingUserId(null)
        }
    }

    const handleCloseSession = async (s: SessionItem) => {
        if (!window.confirm(t.admin.confirmClose(s.id))) return
        setClosingSessionId(s.id)
        try {
            const res = await fetch(`/api/sessions/${s.id}/close`, { method: "POST" })
            if (!res.ok) {
                const data = await res.json()
                setError(data?.detail || t.admin.closeSessionError)
                return
            }
            if (selectedUser) await handleSelectUser(selectedUser)
        } catch {
            setError(t.admin.networkError)
        } finally {
            setClosingSessionId(null)
        }
    }

    const userColumnClass = (selected: boolean, color: string) =>
        `px-4 py-3 transition-colors ${selected ? `bg-${color}-50/60` : "hover:bg-muted/80"}`

    return (
        <>
            <div className="flex flex-col min-h-full bg-muted/50">
                <header className="flex items-center justify-between px-8 py-5 bg-card border-b sticky top-0 z-10 shadow-sm">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-600 shadow-sm">
                            <UserCog className="h-5 w-5 text-white" />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold tracking-tight text-foreground">{t.admin.title}</h1>
                            <p className="text-xs text-muted-foreground">{t.admin.subtitle}</p>
                        </div>
                        <Badge className="bg-indigo-50 text-indigo-700 hover:bg-indigo-50 border border-indigo-200 gap-1 ml-2">
                            <Shield className="h-3 w-3" /> {t.admin.administrator}
                        </Badge>
                    </div>
                    <div className="flex items-center gap-3">
                        <CsvImportDialog onImported={loadAll} />
                        <div className="flex items-center gap-1.5 bg-card border rounded-lg px-3 py-1.5 shadow-sm text-sm">
                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                            <span className="font-medium text-foreground">{users.length + savUsers.length + superviseurUsers.length + adminUsers.length}</span>
                            <span className="text-muted-foreground">{t.admin.usersSuffix}</span>
                        </div>
                    </div>
                </header>

                <div className="p-8 space-y-6 max-w-7xl mx-auto w-full">
                    {error && (
                        <div className="flex items-center gap-2 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-700 dark:text-red-400">
                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                            {error}
                        </div>
                    )}

                    <div className="grid gap-5 lg:grid-cols-5">
                        {/* Utilisateurs */}
                        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                                        <Users className="h-4 w-4 text-blue-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{t.admin.usersPanel.title}</p>
                                        <p className="text-xs text-muted-foreground">{t.admin.usersPanel.subtitle}</p>
                                    </div>
                                </div>
                                <Badge className="bg-blue-50 text-blue-600 border-blue-100 text-xs font-semibold">{users.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {isLoading ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.loading}</div>
                                ) : users.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.usersPanel.empty}</div>
                                ) : users.slice((usersPage - 1) * PAGE_SIZE, usersPage * PAGE_SIZE).map((u) => (
                                    <div key={u.id} className={userColumnClass(selectedUser?.id === u.id, "blue")}>
                                        <button onClick={() => handleSelectUser(u)} className="w-full text-left flex items-center gap-3 mb-2.5">
                                            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                                                <span className="text-xs font-bold text-blue-600">{u.username.charAt(0).toUpperCase()}</span>
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-foreground truncate">{u.username}</div>
                                                <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                                            </div>
                                            {selectedUser?.id === u.id && <ChevronRight className="h-4 w-4 text-blue-400 ml-auto flex-shrink-0" />}
                                        </button>
                                        <div className="flex items-center gap-1.5 pl-11">
                                            <button onClick={() => handleChangeRole(u, "sav")} disabled={updatingRoleUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors disabled:opacity-50">
                                                <UserCheck className="h-3 w-3" />
                                                {updatingRoleUserId === u.id ? "..." : t.admin.promoteToSav}
                                            </button>
                                            <button onClick={() => handleEditUser(u)} disabled={updatingUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-muted text-muted-foreground hover:bg-muted border border-border transition-colors disabled:opacity-50">
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
                                <div className="flex items-center justify-between px-3 py-2 border-t border-border">
                                    <button onClick={() => setUsersPage(p => p - 1)} disabled={usersPage <= 1} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-muted-foreground">{usersPage} / {Math.ceil(users.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setUsersPage(p => p + 1)} disabled={usersPage >= Math.ceil(users.length / PAGE_SIZE)} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Agents SAV */}
                        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
                                        <Headphones className="h-4 w-4 text-emerald-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{t.admin.savPanel.title}</p>
                                        <p className="text-xs text-muted-foreground">{t.admin.savPanel.subtitle}</p>
                                    </div>
                                </div>
                                <Badge className="bg-emerald-50 text-emerald-600 border-emerald-100 text-xs font-semibold">{savUsers.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {isLoading ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.loading}</div>
                                ) : savUsers.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.savPanel.empty}</div>
                                ) : savUsers.slice((savPage - 1) * PAGE_SIZE, savPage * PAGE_SIZE).map((u) => (
                                    <div key={u.id} className={userColumnClass(selectedUser?.id === u.id, "emerald")}>
                                        <button onClick={() => handleSelectUser(u)} className="w-full text-left flex items-center gap-3 mb-2.5">
                                            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                                                <span className="text-xs font-bold text-emerald-600">{u.username.charAt(0).toUpperCase()}</span>
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-foreground truncate">{u.username}</div>
                                                <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                                            </div>
                                            {selectedUser?.id === u.id && <ChevronRight className="h-4 w-4 text-emerald-400 ml-auto flex-shrink-0" />}
                                        </button>
                                        <div className="flex items-center gap-1.5 pl-11">
                                            <button onClick={() => handleChangeRole(u, "user")} disabled={updatingRoleUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-orange-50 text-orange-600 hover:bg-orange-100 border border-orange-200 transition-colors disabled:opacity-50">
                                                <UserX className="h-3 w-3" />
                                                {updatingRoleUserId === u.id ? "..." : t.admin.demote}
                                            </button>
                                            <button onClick={() => handleEditUser(u)} disabled={updatingUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-muted text-muted-foreground hover:bg-muted border border-border transition-colors disabled:opacity-50">
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
                                <div className="flex items-center justify-between px-3 py-2 border-t border-border">
                                    <button onClick={() => setSavPage(p => p - 1)} disabled={savPage <= 1} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-muted-foreground">{savPage} / {Math.ceil(savUsers.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setSavPage(p => p + 1)} disabled={savPage >= Math.ceil(savUsers.length / PAGE_SIZE)} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Superviseurs */}
                        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-violet-50 flex items-center justify-center">
                                        <Shield className="h-4 w-4 text-violet-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{t.admin.supervisorPanel.title}</p>
                                        <p className="text-xs text-muted-foreground">{t.admin.supervisorPanel.subtitle}</p>
                                    </div>
                                </div>
                                <Badge className="bg-violet-50 text-violet-600 border-violet-100 text-xs font-semibold">{superviseurUsers.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {isLoading ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.loading}</div>
                                ) : superviseurUsers.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.supervisorPanel.empty}</div>
                                ) : superviseurUsers.slice((superviseurPage - 1) * PAGE_SIZE, superviseurPage * PAGE_SIZE).map((u) => (
                                    <div key={u.id} className={userColumnClass(selectedUser?.id === u.id, "violet")}>
                                        <button onClick={() => handleSelectUser(u)} className="w-full text-left flex items-center gap-3 mb-2.5">
                                            <div className="w-8 h-8 rounded-full bg-violet-100 flex items-center justify-center flex-shrink-0">
                                                <span className="text-xs font-bold text-violet-600">{u.username.charAt(0).toUpperCase()}</span>
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-foreground truncate">{u.username}</div>
                                                <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                                            </div>
                                            {selectedUser?.id === u.id && <ChevronRight className="h-4 w-4 text-violet-400 ml-auto flex-shrink-0" />}
                                        </button>
                                        <div className="flex items-center gap-1.5 pl-11">
                                            <button onClick={() => handleChangeRole(u, "sav")} disabled={updatingRoleUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-orange-50 text-orange-600 hover:bg-orange-100 border border-orange-200 transition-colors disabled:opacity-50">
                                                <UserX className="h-3 w-3" />
                                                {updatingRoleUserId === u.id ? "..." : t.admin.demote}
                                            </button>
                                            <button onClick={() => handleEditUser(u)} disabled={updatingUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-muted text-muted-foreground hover:bg-muted border border-border transition-colors disabled:opacity-50">
                                                <Pencil className="h-3 w-3" />
                                            </button>
                                            <button onClick={() => handleDeleteUser(u)} disabled={updatingUserId === u.id || currentUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-red-50 text-red-500 hover:bg-red-100 border border-red-200 transition-colors disabled:opacity-50">
                                                <Trash2 className="h-3 w-3" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {Math.ceil(superviseurUsers.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-border">
                                    <button onClick={() => setSuperviseurPage(p => p - 1)} disabled={superviseurPage <= 1} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-muted-foreground">{superviseurPage} / {Math.ceil(superviseurUsers.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setSuperviseurPage(p => p + 1)} disabled={superviseurPage >= Math.ceil(superviseurUsers.length / PAGE_SIZE)} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Admins */}
                        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
                                        <Crown className="h-4 w-4 text-indigo-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{t.admin.adminPanel.title}</p>
                                        <p className="text-xs text-muted-foreground">{t.admin.adminPanel.subtitle}</p>
                                    </div>
                                </div>
                                <Badge className="bg-indigo-50 text-indigo-600 border-indigo-100 text-xs font-semibold">{adminUsers.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {isLoading ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.loading}</div>
                                ) : adminUsers.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.adminPanel.empty}</div>
                                ) : adminUsers.slice((adminPage - 1) * PAGE_SIZE, adminPage * PAGE_SIZE).map((u) => (
                                    <div key={u.id} className={userColumnClass(selectedUser?.id === u.id, "indigo")}>
                                        <button onClick={() => handleSelectUser(u)} className="w-full text-left flex items-center gap-3 mb-2.5">
                                            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                                                <span className="text-xs font-bold text-indigo-600">{u.username.charAt(0).toUpperCase()}</span>
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-foreground truncate">{u.username}</div>
                                                <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                                            </div>
                                            {selectedUser?.id === u.id && <ChevronRight className="h-4 w-4 text-indigo-400 ml-auto flex-shrink-0" />}
                                        </button>
                                        <div className="flex items-center gap-1.5 pl-11">
                                            <button onClick={() => handleEditUser(u)} disabled={updatingUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-muted text-muted-foreground hover:bg-muted border border-border transition-colors disabled:opacity-50">
                                                <Pencil className="h-3 w-3" /> {t.admin.edit}
                                            </button>
                                            <button onClick={() => handleDeleteUser(u)} disabled={updatingUserId === u.id || currentUserId === u.id} className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-red-50 text-red-500 hover:bg-red-100 border border-red-200 transition-colors disabled:opacity-50">
                                                <Trash2 className="h-3 w-3" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {Math.ceil(adminUsers.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-border">
                                    <button onClick={() => setAdminPage(p => p - 1)} disabled={adminPage <= 1} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-muted-foreground">{adminPage} / {Math.ceil(adminUsers.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setAdminPage(p => p + 1)} disabled={adminPage >= Math.ceil(adminUsers.length / PAGE_SIZE)} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Conversations */}
                        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-violet-50 flex items-center justify-center">
                                        <MessageCircle className="h-4 w-4 text-violet-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{t.admin.conversationsTitle}</p>
                                        <p className="text-xs text-muted-foreground">{selectedUser ? selectedUser.username : t.admin.selectUser}</p>
                                    </div>
                                </div>
                                {sessions.length > 0 && (
                                    <Badge className="bg-violet-50 text-violet-600 border-violet-100 text-xs font-semibold">{sessions.length}</Badge>
                                )}
                            </div>
                            {selectedUser && (
                                <div className="px-4 py-2.5 border-b border-border">
                                    <Input
                                        value={sessionQuery}
                                        onChange={(e) => setSessionQuery(e.target.value)}
                                        placeholder={t.admin.searchPlaceholder}
                                        className="h-8 text-sm"
                                    />
                                </div>
                            )}
                            <div className="divide-y divide-slate-50">
                                {!selectedUser ? (
                                    <div className="px-5 py-10 text-center">
                                        <MessageCircle className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                                        <p className="text-sm text-muted-foreground">{t.admin.selectUserPrompt}</p>
                                    </div>
                                ) : sessionQuery.trim() ? (
                                    isSearchingSessions ? (
                                        <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.searching}</div>
                                    ) : !sessionSearchResults || sessionSearchResults.length === 0 ? (
                                        <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.noResultsFor(sessionQuery.trim())}</div>
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
                                                className={`w-full text-left px-4 py-3 transition-colors cursor-pointer ${selectedSession?.id === s.id ? "bg-violet-50/70" : "hover:bg-muted/80"}`}
                                            >
                                                <div className="flex items-start justify-between gap-2">
                                                    <div className="min-w-0">
                                                        <div className="text-sm font-medium text-foreground truncate">{s.title || t.admin.untitled}</div>
                                                        {s.snippet ? (
                                                            <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{renderSnippet(s.snippet)}</div>
                                                        ) : (
                                                            <div className="text-xs text-muted-foreground mt-0.5">#{s.id}</div>
                                                        )}
                                                    </div>
                                                    <div className={`flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full flex-shrink-0 ${s.status === "closed" ? "bg-muted text-muted-foreground" : s.status === "transferred" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                                                        {s.status === "closed" ? <><CheckCircle2 className="h-2.5 w-2.5" /> {t.admin.statusClosed}</>
                                                            : s.status === "transferred" ? <><AlertCircle className="h-2.5 w-2.5" /> {t.admin.statusTransferred}</>
                                                            : <><CircleDot className="h-2.5 w-2.5" /> {t.admin.statusOpen}</>}
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    )
                                ) : sessions.length === 0 ? (
                                    <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.admin.noSessions}</div>
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
                                        className={`w-full text-left px-4 py-3 transition-colors cursor-pointer ${selectedSession?.id === s.id ? "bg-violet-50/70" : "hover:bg-muted/80"}`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-foreground truncate">{s.title || t.admin.untitled}</div>
                                                <div className="text-xs text-muted-foreground mt-0.5">#{s.id}</div>
                                            </div>
                                            <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                                                <div className={`flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full ${s.status === "closed" ? "bg-muted text-muted-foreground" : s.status === "transferred" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                                                    {s.status === "closed" ? <><CheckCircle2 className="h-2.5 w-2.5" /> {t.admin.statusClosed}</>
                                                        : s.status === "transferred" ? <><AlertCircle className="h-2.5 w-2.5" /> {t.admin.statusTransferred}</>
                                                        : <><CircleDot className="h-2.5 w-2.5" /> {t.admin.statusOpen}</>}
                                                </div>
                                                {s.status !== "closed" && (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); handleCloseSession(s) }}
                                                        disabled={closingSessionId === s.id}
                                                        className="text-[11px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground hover:bg-muted border border-border transition-colors disabled:opacity-50"
                                                    >
                                                        {closingSessionId === s.id ? t.admin.closing : t.admin.close}
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {!sessionQuery.trim() && Math.ceil(sessions.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-border">
                                    <button onClick={() => setSessionsPage(p => p - 1)} disabled={sessionsPage <= 1} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-muted-foreground">{sessionsPage} / {Math.ceil(sessions.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setSessionsPage(p => p + 1)} disabled={sessionsPage >= Math.ceil(sessions.length / PAGE_SIZE)} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Platform Overview */}
                    <div className="grid gap-5 lg:grid-cols-3">
                        <div className="lg:col-span-2 bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                    <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
                                        <Headphones className="h-4 w-4 text-amber-600" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{t.admin.transfersTitle}</p>
                                        <p className="text-xs text-muted-foreground">{t.admin.transfersSubtitle}</p>
                                    </div>
                                </div>
                                <Badge className="bg-amber-50 text-amber-600 border-amber-100 text-xs font-semibold">{transferredSessions.length}</Badge>
                            </div>
                            <div className="divide-y divide-slate-50">
                                {transferredSessions.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center py-12 gap-2">
                                        <CheckCircle2 className="h-8 w-8 text-emerald-200" />
                                        <p className="text-sm text-muted-foreground">{t.admin.noTransfers}</p>
                                        <p className="text-xs text-muted-foreground">{t.admin.allUnderControl}</p>
                                    </div>
                                ) : transferredSessions.slice((transfersPage - 1) * PAGE_SIZE, transfersPage * PAGE_SIZE).map((s) => (
                                    <div key={s.id} className="px-5 py-3 flex items-center gap-3">
                                        <div className="w-9 h-9 rounded-full bg-indigo-50 flex items-center justify-center flex-shrink-0 text-xs font-bold text-indigo-600 border-2 border-indigo-100">
                                            {s.username.charAt(0).toUpperCase()}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <div className="text-sm font-medium text-foreground">{s.username}</div>
                                            <div className="text-xs text-muted-foreground truncate">{s.title || t.admin.untitled}</div>
                                        </div>
                                        {s.transfer_reason && (
                                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${REASON_STYLES[s.transfer_reason] ?? "bg-muted text-muted-foreground border-border"}`}>
                                                {reasonLabel(s.transfer_reason)}
                                            </span>
                                        )}
                                        <span className="text-xs text-muted-foreground flex-shrink-0">#{s.id}</span>
                                    </div>
                                ))}
                            </div>
                            {Math.ceil(transferredSessions.length / PAGE_SIZE) > 1 && (
                                <div className="flex items-center justify-between px-3 py-2 border-t border-border">
                                    <button onClick={() => setTransfersPage(p => p - 1)} disabled={transfersPage <= 1} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </button>
                                    <span className="text-xs text-muted-foreground">{transfersPage} / {Math.ceil(transferredSessions.length / PAGE_SIZE)}</span>
                                    <button onClick={() => setTransfersPage(p => p + 1)} disabled={transfersPage >= Math.ceil(transferredSessions.length / PAGE_SIZE)} className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed">
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            )}
                        </div>

                        <div className="space-y-5">
                            <Link href="/analytics" className="block group">
                                <div className="bg-card rounded-xl border border-border shadow-sm p-5 hover:border-indigo-200 hover:shadow-md transition-all">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center group-hover:bg-indigo-100 transition-colors">
                                            <BarChart2 className="h-5 w-5 text-indigo-600" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-foreground">{t.admin.analyticsTitle}</p>
                                            <p className="text-xs text-muted-foreground">{t.admin.analyticsSubtitle}</p>
                                        </div>
                                        <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-indigo-500 transition-colors" />
                                    </div>
                                </div>
                            </Link>
                            <Link href="/knowledge-base" className="block group">
                                <div className="bg-card rounded-xl border border-border shadow-sm p-5 hover:border-emerald-200 hover:shadow-md transition-all">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center group-hover:bg-emerald-100 transition-colors">
                                            <BookOpen className="h-5 w-5 text-emerald-600" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-foreground">{t.admin.kbTitle}</p>
                                            <p className="text-xs text-muted-foreground">{t.admin.kbSubtitle}</p>
                                        </div>
                                        <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-emerald-500 transition-colors" />
                                    </div>
                                </div>
                            </Link>
                            <div className="bg-card rounded-xl border border-border shadow-sm p-5">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center">
                                        <TrendingUp className="h-5 w-5 text-violet-600" />
                                    </div>
                                    <p className="text-sm font-semibold text-foreground">{t.admin.summaryTitle}</p>
                                </div>
                                <div className="space-y-2.5">
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-muted-foreground">{t.admin.clients}</span>
                                        <span className="font-semibold text-foreground">{users.length}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-muted-foreground">{t.admin.savAgents}</span>
                                        <span className="font-semibold text-foreground">{savUsers.length}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-muted-foreground">{t.admin.pendingTransfers}</span>
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
                        <DialogTitle>{t.admin.editUserTitle}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <Label htmlFor="edit-prenom">{t.admin.firstName}</Label>
                                <Input id="edit-prenom" value={editForm.prenom} onChange={(e) => setEditForm((f) => ({ ...f, prenom: e.target.value }))} placeholder={t.admin.firstName} />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="edit-nom">{t.admin.lastName}</Label>
                                <Input id="edit-nom" value={editForm.nom} onChange={(e) => setEditForm((f) => ({ ...f, nom: e.target.value }))} placeholder={t.admin.lastName} />
                            </div>
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="edit-username">{t.admin.username}</Label>
                            <Input id="edit-username" value={editForm.username} onChange={(e) => setEditForm((f) => ({ ...f, username: e.target.value }))} placeholder="username" />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="edit-email">{t.admin.email}</Label>
                            <Input id="edit-email" type="email" value={editForm.email} onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))} placeholder="email@exemple.com" />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="edit-role">{t.admin.role}</Label>
                            <Select value={editForm.role} onValueChange={(v) => setEditForm((f) => ({ ...f, role: v }))}>
                                <SelectTrigger id="edit-role"><SelectValue placeholder={t.admin.chooseRole} /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="user">{t.admin.roleUser}</SelectItem>
                                    <SelectItem value="sav">{t.admin.roleSav}</SelectItem>
                                    <SelectItem value="superviseur">{t.admin.roleSuperviseur}</SelectItem>
                                    <SelectItem value="admin">{t.admin.roleAdmin}</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter className="gap-2">
                        <Button variant="outline" onClick={() => setEditDialogOpen(false)}>{t.admin.cancel}</Button>
                        <Button onClick={handleEditSubmit} disabled={updatingUserId === editingUser?.id || !editForm.username.trim() || !editForm.email.trim()} className="bg-indigo-600 hover:bg-indigo-700 text-white">
                            {updatingUserId === editingUser?.id ? t.admin.saving : t.admin.save}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Dialog */}
            <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t.admin.deleteAccountTitle}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t.admin.deleteAccountIntro}{" "}
                            <span className="font-semibold text-foreground">{deletingUser?.username}</span>{" "}
                            ({deletingUser?.email}). {t.admin.deleteAccountIrreversible}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t.admin.cancel}</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDeleteConfirm} className="bg-red-600 hover:bg-red-700 text-white">
                            {t.admin.delete}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    )
}
