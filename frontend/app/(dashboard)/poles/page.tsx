"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
    Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import {
    AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
    AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { Building2, Loader2, Plus, Pencil, Trash2, Users, ShieldOff } from "lucide-react"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useLocale } from "@/lib/i18n/LocaleContext"
import type { Pole } from "@/lib/poles"

type Manager = { id: number; username: string; email: string; poles: Pole[] }
type SuperviseurOption = { id: number; username: string; email: string }

export default function PolesPage() {
    const { messages: t } = useLocale()
    const { user, isLoading: isLoadingUser } = useCurrentUser()
    const [activeTab, setActiveTab] = useState<"poles" | "managers">("poles")

    const [poles, setPoles] = useState<Pole[]>([])
    const [isLoadingPoles, setIsLoadingPoles] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const [isCreateOpen, setIsCreateOpen] = useState(false)
    const [newPoleName, setNewPoleName] = useState("")
    const [isSaving, setIsSaving] = useState(false)

    const [editingPole, setEditingPole] = useState<Pole | null>(null)
    const [editName, setEditName] = useState("")

    const [deletingPole, setDeletingPole] = useState<Pole | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)

    const [managers, setManagers] = useState<Manager[]>([])
    const [superviseurs, setSuperviseurs] = useState<SuperviseurOption[]>([])
    const [selectedSuperviseurId, setSelectedSuperviseurId] = useState<string>("")
    const [selectedPoleIds, setSelectedPoleIds] = useState<Set<number>>(new Set())
    const [isAssigning, setIsAssigning] = useState(false)
    const [isRemoving, setIsRemoving] = useState<number | null>(null)

    const canManagePoles = !isLoadingUser && !!user && user.role === "admin" && !!user.poles_enabled

    const loadPoles = async () => {
        setIsLoadingPoles(true)
        try {
            const res = await fetch("/api/poles", { credentials: "include" })
            if (res.ok) setPoles(await res.json())
            else if (res.status === 403) setError(t.polesPage.accessDenied)
        } catch {
            setError(t.polesPage.networkError)
        } finally {
            setIsLoadingPoles(false)
        }
    }

    const loadManagersData = async () => {
        try {
            const [managersRes, superviseursRes] = await Promise.all([
                fetch("/api/managers", { credentials: "include" }),
                fetch("/api/users?role=superviseur", { credentials: "include" }),
            ])
            if (managersRes.ok) setManagers(await managersRes.json())
            if (superviseursRes.ok) setSuperviseurs(await superviseursRes.json())
        } catch {
            setError(t.polesPage.networkError)
        }
    }

    useEffect(() => {
        if (!canManagePoles) return
        loadPoles()
        loadManagersData()
        // eslint-disable-next-line react-hooks/exhaustive-deps -- chargement initial une fois les permissions connues
    }, [canManagePoles])

    // Pré-remplit la sélection de pôles avec ceux déjà gérés par le superviseur choisi.
    useEffect(() => {
        if (!selectedSuperviseurId) { setSelectedPoleIds(new Set()); return }
        const existing = managers.find((m) => String(m.id) === selectedSuperviseurId)
        setSelectedPoleIds(new Set(existing ? existing.poles.map((p) => p.id) : []))
    }, [selectedSuperviseurId, managers])

    const handleCreate = async () => {
        if (!newPoleName.trim()) return
        setIsSaving(true)
        setError(null)
        try {
            const res = await fetch("/api/poles", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ nom: newPoleName.trim() }),
            })
            const data = await res.json()
            if (!res.ok) { setError(data?.detail || t.polesPage.networkError); return }
            setNewPoleName("")
            setIsCreateOpen(false)
            await loadPoles()
        } catch {
            setError(t.polesPage.networkError)
        } finally {
            setIsSaving(false)
        }
    }

    const handleRename = async () => {
        if (!editingPole || !editName.trim()) return
        setIsSaving(true)
        setError(null)
        try {
            const res = await fetch(`/api/poles/${editingPole.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ nom: editName.trim() }),
            })
            const data = await res.json()
            if (!res.ok) { setError(data?.detail || t.polesPage.networkError); return }
            setEditingPole(null)
            await loadPoles()
        } catch {
            setError(t.polesPage.networkError)
        } finally {
            setIsSaving(false)
        }
    }

    const handleDeleteConfirm = async () => {
        if (!deletingPole) return
        setIsDeleting(true)
        setError(null)
        try {
            const res = await fetch(`/api/poles/${deletingPole.id}`, { method: "DELETE" })
            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                setError(data?.detail || t.polesPage.networkError)
                return
            }
            setDeletingPole(null)
            await loadPoles()
        } catch {
            setError(t.polesPage.networkError)
        } finally {
            setIsDeleting(false)
        }
    }

    const togglePoleSelection = (poleId: number) => {
        setSelectedPoleIds((prev) => {
            const next = new Set(prev)
            if (next.has(poleId)) next.delete(poleId)
            else next.add(poleId)
            return next
        })
    }

    const handleAssign = async () => {
        if (!selectedSuperviseurId) return
        setIsAssigning(true)
        setError(null)
        try {
            const res = await fetch(`/api/users/${selectedSuperviseurId}/manager-poles`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pole_ids: Array.from(selectedPoleIds) }),
            })
            const data = await res.json()
            if (!res.ok) { setError(data?.detail || t.polesPage.networkError); return }
            setSelectedSuperviseurId("")
            setSelectedPoleIds(new Set())
            await loadManagersData()
        } catch {
            setError(t.polesPage.networkError)
        } finally {
            setIsAssigning(false)
        }
    }

    const handleRemoveManager = async (managerId: number) => {
        setIsRemoving(managerId)
        setError(null)
        try {
            const res = await fetch(`/api/users/${managerId}/manager-poles`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pole_ids: [] }),
            })
            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                setError(data?.detail || t.polesPage.networkError)
                return
            }
            await loadManagersData()
        } catch {
            setError(t.polesPage.networkError)
        } finally {
            setIsRemoving(null)
        }
    }

    if (isLoadingUser) {
        return (
            <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    // Retro-compat : flag off ou rôle non-admin -> aucune UI, message court plutôt qu'une
    // page qui plante ou qui affiche des données auxquelles l'utilisateur n'a pas droit.
    if (!canManagePoles) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-2 p-8">
                <ShieldOff className="h-10 w-10 opacity-30" />
                <p className="text-sm">
                    {!user?.poles_enabled ? t.polesPage.featureDisabled : t.polesPage.accessDenied}
                </p>
            </div>
        )
    }

    const assignablePoles = poles.filter((p) => !p.is_global)

    return (
        <div className="p-8 space-y-6 max-w-4xl mx-auto w-full">
            <div>
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                    <Building2 className="h-6 w-6 text-brand" />
                    {t.polesPage.title}
                </h1>
                <p className="text-sm text-muted-foreground mt-1">{t.polesPage.subtitle}</p>
            </div>

            {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm px-4 py-2.5">
                    {error}
                </div>
            )}

            <div className="flex items-center gap-2 border-b">
                <button
                    type="button"
                    onClick={() => setActiveTab("poles")}
                    className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                        activeTab === "poles" ? "border-brand text-brand" : "border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                >
                    {t.polesPage.tabPoles}
                </button>
                <button
                    type="button"
                    onClick={() => setActiveTab("managers")}
                    className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                        activeTab === "managers" ? "border-brand text-brand" : "border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                >
                    {t.polesPage.tabManagers}
                </button>
            </div>

            {activeTab === "poles" && (
                <div className="space-y-4">
                    <div className="flex justify-end">
                        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                            <Button onClick={() => setIsCreateOpen(true)}>
                                <Plus className="mr-2 h-4 w-4" />
                                {t.polesPage.newPole}
                            </Button>
                            <DialogContent className="sm:max-w-sm">
                                <DialogHeader><DialogTitle>{t.polesPage.newPole}</DialogTitle></DialogHeader>
                                <div className="py-2 space-y-1.5">
                                    <Label htmlFor="new-pole-name">{t.polesPage.poleNamePlaceholder}</Label>
                                    <Input
                                        id="new-pole-name"
                                        value={newPoleName}
                                        onChange={(e) => setNewPoleName(e.target.value)}
                                        placeholder={t.polesPage.poleNamePlaceholder}
                                        onKeyDown={(e) => { if (e.key === "Enter") handleCreate() }}
                                    />
                                </div>
                                <DialogFooter className="gap-2">
                                    <Button variant="outline" onClick={() => setIsCreateOpen(false)}>{t.polesPage.cancel}</Button>
                                    <Button onClick={handleCreate} disabled={isSaving || !newPoleName.trim()} className="bg-brand hover:brightness-90 text-white">
                                        {isSaving ? t.polesPage.creating : t.polesPage.create}
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>

                    {isLoadingPoles ? (
                        <div className="flex justify-center py-10"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
                    ) : poles.length === 0 ? (
                        <div className="text-center text-sm text-muted-foreground py-10">{t.polesPage.noPoles}</div>
                    ) : (
                        <div className="space-y-2">
                            {poles.map((pole) => (
                                <Card key={pole.id}>
                                    <CardContent className="p-4 flex items-center justify-between gap-3">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <span className="font-medium truncate">{pole.nom}</span>
                                            {pole.is_global && <Badge variant="secondary">{t.polesPage.globalBadge}</Badge>}
                                        </div>
                                        <div className="flex items-center gap-1 flex-shrink-0">
                                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { setEditingPole(pole); setEditName(pole.nom) }}>
                                                <Pencil className="h-4 w-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-8 w-8 text-muted-foreground hover:text-destructive disabled:opacity-30"
                                                disabled={pole.is_global}
                                                title={pole.is_global ? t.polesPage.globalCannotDelete : undefined}
                                                onClick={() => setDeletingPole(pole)}
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {activeTab === "managers" && (
                <div className="space-y-6">
                    <Card>
                        <CardContent className="p-5 space-y-4">
                            <div>
                                <h2 className="font-semibold flex items-center gap-2"><Users className="h-4 w-4" />{t.polesPage.managersTitle}</h2>
                                <p className="text-xs text-muted-foreground mt-1">{t.polesPage.managersDesc}</p>
                            </div>

                            <div className="space-y-1.5">
                                <Label>{t.polesPage.selectSuperviseur}</Label>
                                {superviseurs.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">{t.polesPage.noSuperviseurs}</p>
                                ) : (
                                    <Select value={selectedSuperviseurId} onValueChange={setSelectedSuperviseurId}>
                                        <SelectTrigger><SelectValue placeholder={t.polesPage.selectSuperviseur} /></SelectTrigger>
                                        <SelectContent>
                                            {superviseurs.map((s) => (
                                                <SelectItem key={s.id} value={String(s.id)}>{s.username} ({s.email})</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                )}
                            </div>

                            {selectedSuperviseurId && (
                                <div className="space-y-1.5">
                                    <Label>{t.polesPage.selectPoles}</Label>
                                    {assignablePoles.length === 0 ? (
                                        <p className="text-sm text-muted-foreground">{t.polesPage.noPoles}</p>
                                    ) : (
                                        <div className="space-y-1.5">
                                            {assignablePoles.map((pole) => (
                                                <label key={pole.id} className="flex items-center gap-2 text-sm cursor-pointer">
                                                    <input
                                                        type="checkbox"
                                                        className="h-4 w-4 accent-brand rounded cursor-pointer"
                                                        checked={selectedPoleIds.has(pole.id)}
                                                        onChange={() => togglePoleSelection(pole.id)}
                                                    />
                                                    {pole.nom}
                                                </label>
                                            ))}
                                            <p className="text-xs text-muted-foreground">{t.polesPage.globalNotAssignable}</p>
                                        </div>
                                    )}
                                </div>
                            )}

                            <Button onClick={handleAssign} disabled={!selectedSuperviseurId || isAssigning} className="bg-brand hover:brightness-90 text-white">
                                {isAssigning ? t.polesPage.assigning : t.polesPage.assign}
                            </Button>
                        </CardContent>
                    </Card>

                    <div className="space-y-2">
                        <h3 className="text-sm font-semibold text-muted-foreground">{t.polesPage.currentManagers}</h3>
                        {managers.length === 0 ? (
                            <p className="text-sm text-muted-foreground">{t.polesPage.noManagers}</p>
                        ) : (
                            managers.map((manager) => (
                                <Card key={manager.id}>
                                    <CardContent className="p-4 flex items-center justify-between gap-3">
                                        <div className="min-w-0">
                                            <p className="font-medium truncate">{manager.username}</p>
                                            <div className="flex flex-wrap gap-1 mt-1">
                                                {manager.poles.map((p) => (
                                                    <Badge key={p.id} variant="secondary" className="text-xs">{p.nom}</Badge>
                                                ))}
                                            </div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-muted-foreground hover:text-destructive flex-shrink-0"
                                            disabled={isRemoving === manager.id}
                                            onClick={() => handleRemoveManager(manager.id)}
                                        >
                                            {isRemoving === manager.id ? <Loader2 className="h-4 w-4 animate-spin" /> : t.polesPage.removeManager}
                                        </Button>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </div>
                </div>
            )}

            {/* Rename dialog */}
            <Dialog open={!!editingPole} onOpenChange={(open) => { if (!open) setEditingPole(null) }}>
                <DialogContent className="sm:max-w-sm">
                    <DialogHeader><DialogTitle>{t.polesPage.rename}</DialogTitle></DialogHeader>
                    <div className="py-2 space-y-1.5">
                        <Label htmlFor="rename-pole">{t.polesPage.poleNamePlaceholder}</Label>
                        <Input
                            id="rename-pole"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            onKeyDown={(e) => { if (e.key === "Enter") handleRename() }}
                        />
                    </div>
                    <DialogFooter className="gap-2">
                        <Button variant="outline" onClick={() => setEditingPole(null)}>{t.polesPage.cancel}</Button>
                        <Button onClick={handleRename} disabled={isSaving || !editName.trim()} className="bg-brand hover:brightness-90 text-white">
                            {isSaving ? t.polesPage.renaming : t.polesPage.save}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete confirmation */}
            <AlertDialog open={!!deletingPole} onOpenChange={(open) => { if (!open) setDeletingPole(null) }}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t.polesPage.confirmDeleteTitle}</AlertDialogTitle>
                        <AlertDialogDescription>
                            <span className="font-medium text-foreground">{deletingPole?.nom}</span> — {t.polesPage.confirmDeleteBody}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isDeleting}>{t.polesPage.cancel}</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDeleteConfirm}
                            disabled={isDeleting}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {isDeleting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                            {isDeleting ? t.polesPage.deleting : t.polesPage.delete}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
