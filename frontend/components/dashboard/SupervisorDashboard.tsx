"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Users, Headphones, UserCheck, UserX, ChevronLeft, ChevronRight, ShieldCheck } from "lucide-react"
import type { UserItem } from "./types"
import SavDashboard from "./SavDashboard"
import { useLocale } from "@/lib/i18n/LocaleContext"

const PAGE_SIZE = 8

export default function SupervisorDashboard() {
    const { messages: t } = useLocale()
    const [users, setUsers] = useState<UserItem[]>([])
    const [savUsers, setSavUsers] = useState<UserItem[]>([])
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [updatingUserId, setUpdatingUserId] = useState<number | null>(null)
    const [usersPage, setUsersPage] = useState(1)
    const [savPage, setSavPage] = useState(1)

    const loadTeam = async () => {
        setIsLoading(true)
        setError(null)
        try {
            const [usersRes, savRes] = await Promise.all([
                fetch("/api/users?role=user"),
                fetch("/api/users?role=sav"),
            ])
            if (usersRes.status === 401 || savRes.status === 401) {
                setError(t.supervisor.sessionExpired)
                return
            }
            if (!usersRes.ok || !savRes.ok) {
                setError(t.supervisor.loadTeamError)
                return
            }
            setUsers(await usersRes.json())
            setSavUsers(await savRes.json())
        } catch {
            setError(t.supervisor.networkError)
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        loadTeam()
    }, [])

    const handleChangeRole = async (u: UserItem, newRole: "user" | "sav") => {
        setError(null)
        setUpdatingUserId(u.id)
        try {
            const res = await fetch(`/api/users/${u.id}/role`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ role: newRole }),
            })
            const data = await res.json()
            if (!res.ok) {
                setError(res.status === 401 ? t.supervisor.sessionExpired : data?.detail || t.supervisor.roleChangeError)
                return
            }
            await loadTeam()
        } catch {
            setError(t.supervisor.networkError)
        } finally {
            setUpdatingUserId(null)
        }
    }

    return (
        <div className="flex flex-col min-h-full bg-muted/50">
            <header className="flex items-center justify-between px-8 py-5 bg-card border-b shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-600 shadow-sm">
                        <ShieldCheck className="h-5 w-5 text-white" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold tracking-tight text-foreground">{t.supervisor.title}</h1>
                        <p className="text-xs text-muted-foreground">{t.supervisor.subtitle}</p>
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

                <div className="grid gap-5 lg:grid-cols-2">
                    {/* Utilisateurs */}
                    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                                <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                                    <Users className="h-4 w-4 text-blue-600" />
                                </div>
                                <div>
                                    <p className="text-sm font-semibold text-foreground">{t.supervisor.usersTitle}</p>
                                    <p className="text-xs text-muted-foreground">{t.supervisor.usersSubtitle}</p>
                                </div>
                            </div>
                            <Badge className="bg-blue-50 text-blue-600 border-blue-100 text-xs font-semibold">{users.length}</Badge>
                        </div>
                        <div className="divide-y divide-slate-50">
                            {isLoading ? (
                                <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.supervisor.loading}</div>
                            ) : users.length === 0 ? (
                                <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.supervisor.noUsers}</div>
                            ) : users.slice((usersPage - 1) * PAGE_SIZE, usersPage * PAGE_SIZE).map((u) => (
                                <div key={u.id} className="px-4 py-3 flex items-center justify-between hover:bg-muted/80">
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                                            <span className="text-xs font-bold text-blue-600">{u.username.charAt(0).toUpperCase()}</span>
                                        </div>
                                        <div className="min-w-0">
                                            <div className="text-sm font-medium text-foreground truncate">{u.username}</div>
                                            <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleChangeRole(u, "sav")}
                                        disabled={updatingUserId === u.id}
                                        className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors disabled:opacity-50 flex-shrink-0"
                                    >
                                        <UserCheck className="h-3 w-3" />
                                        {updatingUserId === u.id ? "..." : t.supervisor.promote}
                                    </button>
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
                                    <p className="text-sm font-semibold text-foreground">{t.supervisor.savTitle}</p>
                                    <p className="text-xs text-muted-foreground">{t.supervisor.savSubtitle}</p>
                                </div>
                            </div>
                            <Badge className="bg-emerald-50 text-emerald-600 border-emerald-100 text-xs font-semibold">{savUsers.length}</Badge>
                        </div>
                        <div className="divide-y divide-slate-50">
                            {isLoading ? (
                                <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.supervisor.loading}</div>
                            ) : savUsers.length === 0 ? (
                                <div className="px-5 py-8 text-center text-sm text-muted-foreground">{t.supervisor.noSav}</div>
                            ) : savUsers.slice((savPage - 1) * PAGE_SIZE, savPage * PAGE_SIZE).map((u) => (
                                <div key={u.id} className="px-4 py-3 flex items-center justify-between hover:bg-muted/80">
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                                            <span className="text-xs font-bold text-emerald-600">{u.username.charAt(0).toUpperCase()}</span>
                                        </div>
                                        <div className="min-w-0">
                                            <div className="text-sm font-medium text-foreground truncate">{u.username}</div>
                                            <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleChangeRole(u, "user")}
                                        disabled={updatingUserId === u.id}
                                        className="flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-orange-50 text-orange-600 hover:bg-orange-100 border border-orange-200 transition-colors disabled:opacity-50 flex-shrink-0"
                                    >
                                        <UserX className="h-3 w-3" />
                                        {updatingUserId === u.id ? "..." : t.supervisor.demote}
                                    </button>
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
                </div>
            </div>

            {/* File d'attente SAV — un superviseur reste aussi un agent, il traite les tickets transférés */}
            <div className="flex-1 min-h-[600px] border-t border-border">
                <SavDashboard />
            </div>
        </div>
    )
}
