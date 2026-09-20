"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Upload, Loader2 } from "lucide-react"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { isManager, isPoleUnrestricted, type Pole } from "@/lib/poles"

type ImportResult = {
    total_rows: number
    created: number
    skipped: { row: number; email: string; reason: string }[]
}

export function CsvImportDialog({ onImported }: { onImported: () => void }) {
    const { user } = useCurrentUser()
    const [open, setOpen] = useState(false)
    const [file, setFile] = useState<File | null>(null)
    const [isImporting, setIsImporting] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [result, setResult] = useState<ImportResult | null>(null)
    const fileInputRef = useRef<HTMLInputElement | null>(null)

    // Système de pôles (feature/poles, étape 5) : un manager choisit parmi SES pôles
    // (déjà connus via /me, pas d'appel réseau requis) ; un compte pole-unrestricted
    // (admin, ou superviseur non-manager) choisit parmi tous les pôles existants. Aucun
    // champ n'apparaît si la feature est désactivée -- comportement actuel identique.
    const unrestricted = isPoleUnrestricted(user)
    const manager = isManager(user)
    const [allPoles, setAllPoles] = useState<Pole[]>([])
    const [selectedPoleId, setSelectedPoleId] = useState<string>("")

    useEffect(() => {
        if (!user?.poles_enabled || !unrestricted) return
        fetch("/api/poles", { credentials: "include" })
            .then((res) => (res.ok ? res.json() : []))
            .then((data: Pole[]) => {
                setAllPoles(data)
                const general = data.find((p) => p.is_global)
                setSelectedPoleId(general ? String(general.id) : "")
            })
            .catch(() => {})
    }, [user?.poles_enabled, unrestricted])

    const managerPoles = user?.managed_poles ?? []
    const managerPoleCount = managerPoles.length
    useEffect(() => {
        if (manager && managerPoleCount === 1) setSelectedPoleId(String(managerPoles[0].id))
        // eslint-disable-next-line react-hooks/exhaustive-deps -- managerPoles est un nouveau tableau à chaque rendu (dérivé de user), managerPoleCount (primitif) est la dépendance stable qui capture réellement ce dont cet effet a besoin
    }, [manager, managerPoleCount])

    const poleOptions = unrestricted ? allPoles : managerPoles
    const showPoleSelector = !!user?.poles_enabled && poleOptions.length > 1

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setError(null)
        setResult(null)
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0])
        }
    }

    const handleImport = async () => {
        if (!file) return
        setIsImporting(true)
        setError(null)
        try {
            const formData = new FormData()
            formData.append("file", file)
            if (user?.poles_enabled && selectedPoleId) formData.append("pole_id", selectedPoleId)
            const response = await fetch("/api/users/import-csv", {
                method: "POST",
                credentials: "include",
                body: formData,
            })
            const data = await response.json()
            if (!response.ok) {
                setError(typeof data?.detail === "string" ? data.detail : "Impossible d'importer le fichier.")
                return
            }
            setResult(data)
            onImported()
        } catch {
            setError("Erreur réseau lors de l'import.")
        } finally {
            setIsImporting(false)
        }
    }

    const handleOpenChange = (next: boolean) => {
        setOpen(next)
        if (!next) {
            setFile(null)
            setError(null)
            setResult(null)
        }
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                    <Upload className="mr-2 h-4 w-4" />
                    Importer un CSV
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[480px]">
                <DialogHeader>
                    <DialogTitle>Importer des utilisateurs via CSV</DialogTitle>
                    <DialogDescription>
                        Colonnes attendues : <code>email</code>, <code>username</code>, <code>prenom</code>, <code>nom</code>.
                        Chaque utilisateur créé reçoit un email pour choisir son mot de passe et se connecter.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-3 py-2">
                    <div
                        className="border-2 border-dashed border-muted-foreground/25 rounded-xl p-6 flex flex-col items-center justify-center text-center hover:bg-muted/30 transition-colors cursor-pointer"
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <Upload className="h-6 w-6 text-primary mb-2" />
                        <p className="text-sm font-medium">
                            {file ? file.name : "Cliquez pour sélectionner un fichier .csv"}
                        </p>
                        <input
                            ref={fileInputRef}
                            type="file"
                            className="hidden"
                            accept=".csv,text/csv"
                            onChange={handleFileChange}
                        />
                    </div>

                    {showPoleSelector && (
                        <div className="space-y-1.5">
                            <Label htmlFor="csv-import-pole">Pôle</Label>
                            <Select value={selectedPoleId} onValueChange={setSelectedPoleId}>
                                <SelectTrigger id="csv-import-pole"><SelectValue placeholder="Choisir un pôle" /></SelectTrigger>
                                <SelectContent>
                                    {poleOptions.map((p) => (
                                        <SelectItem key={p.id} value={String(p.id)}>
                                            {p.nom}{p.is_global ? " (commun)" : ""}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    )}

                    {error && <p className="text-sm text-red-600">{error}</p>}

                    {result && (
                        <div className="rounded-lg border bg-muted/30 p-3 space-y-2 text-sm">
                            <p className="font-medium text-emerald-700">
                                {result.created} compte{result.created > 1 ? "s" : ""} créé{result.created > 1 ? "s" : ""} sur {result.total_rows} ligne{result.total_rows > 1 ? "s" : ""}.
                            </p>
                            {result.skipped.length > 0 && (
                                <div className="space-y-1">
                                    <p className="text-amber-700 font-medium">
                                        {result.skipped.length} ligne{result.skipped.length > 1 ? "s" : ""} ignorée{result.skipped.length > 1 ? "s" : ""} :
                                    </p>
                                    <ul className="max-h-32 overflow-y-auto space-y-0.5 text-xs text-muted-foreground">
                                        {result.skipped.map((s, i) => (
                                            <li key={i}>Ligne {s.row} ({s.email || "?"}) — {s.reason}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button onClick={handleImport} disabled={!file || isImporting || (showPoleSelector && !selectedPoleId)}>
                        {isImporting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {isImporting ? "Import..." : "Importer"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
