"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Search,
    Plus,
    FileText,
    Upload,
    Loader2,
    Globe,
    DatabaseZap,
    Cpu,
    Trash2,
    ShieldCheck,
    ShieldAlert,
    Link as LinkIcon,
} from "lucide-react"
import { Progress } from "@/components/ui/progress"

export default function KnowledgeBasePage() {
    const INGEST_POLL_FAST_MS = 5000
    const INGEST_POLL_SLOW_MS = 15000
    const INGEST_POLL_SLOW_AFTER_MS = 60000

    const [searchQuery, setSearchQuery] = useState("")
    const [activeFilter, setActiveFilter] = useState("Tout")
    const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
    const [newArticle, setNewArticle] = useState({
        title: "",
        category: "Guides",
        summary: "",
        tags: "",
        fileName: ""
    })
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [isUploadingFile, setIsUploadingFile] = useState(false)
    const [uploadError, setUploadError] = useState<string | null>(null)
    const [sourceUrl, setSourceUrl] = useState("https://www.service-public.fr/particuliers/vosdroits/F1342")
    const [isIngesting, setIsIngesting] = useState(false)
    const [ingestMessage, setIngestMessage] = useState<string | null>(null)
    const [ingestError, setIngestError] = useState<string | null>(null)
    const [ingestJobId, setIngestJobId] = useState<string | null>(null)
    const ingestPollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const ingestStartedAtRef = useRef<number | null>(null)
    const fileInputRef = useRef<HTMLInputElement | null>(null)

    type RobotsInfo = { robots_found: boolean; sitemap_found: boolean; total: number; allowed: number; blocked: number }
    const [robotsInfo, setRobotsInfo] = useState<RobotsInfo | null>(null)
    const [isCheckingRobots, setIsCheckingRobots] = useState(false)
    const [robotsError, setRobotsError] = useState<string | null>(null)
    const [urlsTotal, setUrlsTotal] = useState<number | null>(null)
    const [urlsDone, setUrlsDone] = useState<number | null>(null)

    type KBSource = { source: string; category: string | null; chunks: number; date_creation: string | null }
    const [kbSources, setKbSources] = useState<KBSource[]>([])
    const [deleteSource, setDeleteSource] = useState<KBSource | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)

    const handleDeleteConfirm = async () => {
        if (!deleteSource) return
        setIsDeleting(true)
        try {
            await fetch(`/api/knowledge-base/sources?source=${encodeURIComponent(deleteSource.source)}`, {
                method: "DELETE",
                credentials: "include",
            })
            setDeleteSource(null)
            await loadSources()
        } finally {
            setIsDeleting(false)
        }
    }

    const loadSources = async () => {
        try {
            const res = await fetch("/api/knowledge-base/sources", { credentials: "include" })
            if (res.ok) setKbSources(await res.json())
        } catch { /* silent */ }
    }

    useEffect(() => { loadSources() }, [])

    useEffect(() => {
        if (!ingestJobId) return

        if (ingestPollRef.current) {
            clearTimeout(ingestPollRef.current)
        }

        const pollStatus = async () => {
            try {
                const response = await fetch(`/api/knowledge-base/ingest-status?job_id=${ingestJobId}`, {
                    credentials: "include",
                })
                if (response.status === 401) {
                    setIsIngesting(false)
                    setIngestJobId(null)
                    ingestStartedAtRef.current = null
                    setIngestError("Session expirée. Veuillez vous reconnecter.")
                    window.location.href = "/login"
                    return
                }
                if (!response.ok) {
                    scheduleNextPoll()
                    return
                }
                const data = await response.json()

                // Mise à jour de la progression en temps réel
                if (typeof data.urls_total === "number") setUrlsTotal(data.urls_total)
                if (typeof data.urls_done === "number") setUrlsDone(data.urls_done)

                if (data.status === "completed") {
                    setIsIngesting(false)
                    setIsUploadingFile(false)
                    setIngestJobId(null)
                    ingestStartedAtRef.current = null
                    setUrlsTotal(null)
                    setUrlsDone(null)
                    if (data.result?.inserted === 0) {
                        setIngestError("Aucun contenu récupéré. Le site bloque peut-être le scraping ou utilise du contenu dynamique.")
                    } else {
                        const inserted = data.result?.inserted ?? "?"
                        const source = data.result?.filename ?? data.result?.url ?? sourceUrl
                        setIngestMessage(`Indexation terminée : ${inserted} contenus indexés depuis ${source}`)
                        loadSources()
                    }
                    return
                }
                if (data.status === "failed") {
                    setIsIngesting(false)
                    setIsUploadingFile(false)
                    setIngestJobId(null)
                    ingestStartedAtRef.current = null
                    setUrlsTotal(null)
                    setUrlsDone(null)
                    setIngestError(data.error || "Erreur pendant l'indexation.")
                    return
                }
            } catch {
                // On ignore pour éviter de spammer l'UI
            }

            scheduleNextPoll()
        }

        const scheduleNextPoll = () => {
            const startedAt = ingestStartedAtRef.current ?? Date.now()
            const elapsed = Date.now() - startedAt
            const nextDelay = elapsed >= INGEST_POLL_SLOW_AFTER_MS ? INGEST_POLL_SLOW_MS : INGEST_POLL_FAST_MS
            ingestPollRef.current = setTimeout(() => {
                void pollStatus()
            }, nextDelay)
        }

        void pollStatus()

        return () => {
            if (ingestPollRef.current) {
                clearTimeout(ingestPollRef.current)
                ingestPollRef.current = null
            }
        }
    }, [ingestJobId, sourceUrl])

    const handleCheckRobots = async () => {
        if (!sourceUrl.trim()) return
        setRobotsInfo(null)
        setRobotsError(null)
        setIsCheckingRobots(true)
        try {
            const res = await fetch(`/api/knowledge-base/robots-check?url=${encodeURIComponent(sourceUrl)}`, {
                credentials: "include",
            })
            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                setRobotsError(data?.detail || "Impossible d'analyser le site.")
                return
            }
            setRobotsInfo(await res.json())
        } catch {
            setRobotsError("Erreur réseau lors de l'analyse.")
        } finally {
            setIsCheckingRobots(false)
        }
    }

    const handleIngestUrl = async () => {
        setIngestMessage(null)
        setIngestError(null)

        setIsIngesting(true)
        let isBackgroundJob = false
        try {
            const response = await fetch("/api/knowledge-base/ingest-url", {
                method: "POST",
                credentials: "include",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ url: sourceUrl }),
            })

            const data = await response.json()
            if (!response.ok) {
                if (response.status === 401) {
                    setIngestError("Session expirée. Veuillez vous reconnecter.")
                    return
                }
                setIngestError(data?.detail || "Impossible de lancer l'ingestion.")
                return
            }

            if (data.status === "started") {
                isBackgroundJob = true
                setIngestMessage(data.message || "Indexation lancée.")
                ingestStartedAtRef.current = Date.now()
                setIngestJobId(data.job_id || null)
                return
            }

            if (data.inserted === 0) {
                setIngestError("Aucun contenu récupéré. Le site bloque peut-être le scraping ou utilise du contenu dynamique.")
                return
            }
            setIngestMessage(`${data.inserted} contenus indexés depuis ${data.url}`)
        } catch (error) {
            console.error("Erreur ingestion URL:", error)
            setIngestError("Erreur réseau pendant l'ingestion.")
        } finally {
            if (!isBackgroundJob) {
                setIsIngesting(false)
                ingestStartedAtRef.current = null
            }
        }
    }

    const handleAddArticle = async () => {
        setUploadError(null)

        if (!selectedFile) {
            setUploadError("Veuillez sélectionner un fichier .pdf, .docx ou .txt.")
            return
        }
        const ext = selectedFile.name.split(".").pop()?.toLowerCase()
        if (ext !== "docx" && ext !== "txt" && ext !== "pdf") {
            setUploadError("Seuls les fichiers .pdf, .docx et .txt sont acceptés.")
            return
        }

        const formData = new FormData()
        formData.append("file", selectedFile)
        if (newArticle.category) formData.append("category", newArticle.category)

        setIsUploadingFile(true)
        setIngestMessage(null)
        setIngestError(null)

        try {
            const response = await fetch("/api/knowledge-base/ingest-file", {
                method: "POST",
                credentials: "include",
                body: formData,
            })
            const data = await response.json()
            if (!response.ok) {
                setUploadError(data?.detail || "Erreur lors de l'envoi du fichier.")
                setIsUploadingFile(false)
                return
            }
            if (data.status === "started") {
                setIngestMessage(data.message || "Indexation du fichier lancée.")
                ingestStartedAtRef.current = Date.now()
                setIngestJobId(data.job_id || null)
                setIsAddDialogOpen(false)
                setNewArticle({ title: "", category: "Guides", summary: "", tags: "", fileName: "" })
                setSelectedFile(null)
            }
        } catch {
            setUploadError("Erreur réseau lors de l'envoi du fichier.")
            setIsUploadingFile(false)
        }
    }

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0]
            setSelectedFile(file)
            setNewArticle({ ...newArticle, fileName: file.name })
            setUploadError(null)
        }
    }

    const uniqueCategories = Array.from(new Set(kbSources.map(s => s.category).filter(Boolean))) as string[]

    const filteredSources = kbSources.filter(s => {
        const matchesSearch = s.source.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (s.category ?? "").toLowerCase().includes(searchQuery.toLowerCase())
        const matchesFilter = activeFilter === "Tout" || s.category === activeFilter
        return matchesSearch && matchesFilter
    })

    return (
        <>
        <div className="flex flex-col min-h-full">
            {/* Header & Search */}
            <div className="p-8 pb-4 space-y-6 bg-background border-b">
                <div className="flex items-center justify-between">
                    <h1 className="text-2xl font-bold tracking-tight">Base de connaissances</h1>
                    <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
                        <DialogTrigger asChild>
                            <Button>
                                <Plus className="mr-2 h-4 w-4" />
                                Ajouter un article
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[500px]">
                            <DialogHeader>
                                <DialogTitle>Ajouter un nouvel article</DialogTitle>
                                <DialogDescription>
                                    Ajoutez du contenu manuellement ou importez un document.
                                </DialogDescription>
                            </DialogHeader>

                            <div className="grid gap-4 py-4">
                                <div className="grid gap-2">
                                    <Label htmlFor="title">Titre</Label>
                                    <Input
                                        id="title"
                                        value={newArticle.title}
                                        onChange={(e) => setNewArticle({ ...newArticle, title: e.target.value })}
                                        placeholder="Titre de l'article"
                                    />
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="category">Catégorie</Label>
                                    <Select
                                        value={newArticle.category}
                                        onValueChange={(value) => setNewArticle({ ...newArticle, category: value })}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Sélectionner une catégorie" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="FAQ">FAQ</SelectItem>
                                            <SelectItem value="Guides">Guides</SelectItem>
                                            <SelectItem value="Documentation">Documentation</SelectItem>
                                            <SelectItem value="Formés IA">Formés IA</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="tags">Tags</Label>
                                    <Input
                                        id="tags"
                                        value={newArticle.tags}
                                        onChange={(e) => setNewArticle({ ...newArticle, tags: e.target.value })}
                                        placeholder="Ex: API, Tutoriel"
                                    />
                                </div>

                                <div className="space-y-4">
                                    <div
                                        className="border-2 border-dashed border-muted-foreground/25 rounded-xl p-8 flex flex-col items-center justify-center text-center hover:bg-muted/30 transition-colors cursor-pointer"
                                        onClick={() => fileInputRef.current?.click()}
                                    >
                                        <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                                            <Upload className="h-6 w-6 text-primary" />
                                        </div>
                                        <p className="text-sm font-medium">
                                            {newArticle.fileName ? newArticle.fileName : "Cliquez pour importer un fichier"}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">
                                            PDF, DOCX ou TXT jusqu&apos;à 10MB
                                        </p>
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            className="hidden"
                                            onChange={handleFileChange}
                                            accept=".pdf,.docx,.txt"
                                        />
                                    </div>
                                    {uploadError && <p className="text-sm text-red-600">{uploadError}</p>}
                                </div>
                            </div>

                            <DialogFooter>
                                <Button onClick={handleAddArticle} disabled={isUploadingFile || !selectedFile}>
                                    {isUploadingFile && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    {isUploadingFile ? "Envoi..." : "Importer et indexer"}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>

                <div className="relative">
                    <Search className="absolute left-3.5 top-3.5 h-5 w-5 text-muted-foreground" />
                    <Input
                        placeholder="Rechercher dans la base de connaissances..."
                        className="pl-12 h-12 text-lg rounded-xl bg-muted/30 border-muted-foreground/20 focus-visible:bg-background"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <div className="rounded-xl border bg-card p-4 space-y-3">
                    <Label htmlFor="source-url">Indexer une URL dans la base</Label>
                    <div className="flex flex-col md:flex-row gap-3">
                        <Input
                            id="source-url"
                            placeholder="https://..."
                            value={sourceUrl}
                            onChange={(e) => { setSourceUrl(e.target.value); setRobotsInfo(null); setRobotsError(null) }}
                        />
                        <Button
                            variant="outline"
                            onClick={handleCheckRobots}
                            disabled={isCheckingRobots || !sourceUrl.trim()}
                        >
                            {isCheckingRobots
                                ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                : <ShieldCheck className="mr-2 h-4 w-4" />}
                            {isCheckingRobots ? "Analyse..." : "Vérifier robots.txt"}
                        </Button>
                        <Button onClick={handleIngestUrl} disabled={isIngesting || !sourceUrl.trim()}>
                            {isIngesting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            {isIngesting ? "Indexation..." : "Indexer URL"}
                        </Button>
                    </div>

                    {/* Résultat robots.txt */}
                    {robotsError && (
                        <p className="text-sm text-red-600 flex items-center gap-1.5">
                            <ShieldAlert className="h-4 w-4 flex-shrink-0" /> {robotsError}
                        </p>
                    )}
                    {robotsInfo && (
                        <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                            <div className="flex flex-wrap items-center gap-4 text-sm">
                                <span className="flex items-center gap-1.5 font-medium text-slate-700">
                                    <LinkIcon className="h-4 w-4 text-slate-400" />
                                    {robotsInfo.sitemap_found ? "Sitemap détecté" : "Pas de sitemap (URL unique)"}
                                    {!robotsInfo.robots_found && <span className="text-xs text-muted-foreground ml-1">(robots.txt absent)</span>}
                                </span>
                                <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                                    <ShieldCheck className="h-4 w-4" />
                                    {robotsInfo.allowed} URL{robotsInfo.allowed > 1 ? "s" : ""} autorisée{robotsInfo.allowed > 1 ? "s" : ""}
                                </span>
                                {robotsInfo.blocked > 0 && (
                                    <span className="flex items-center gap-1 text-red-600 font-semibold">
                                        <ShieldAlert className="h-4 w-4" />
                                        {robotsInfo.blocked} bloquée{robotsInfo.blocked > 1 ? "s" : ""}
                                    </span>
                                )}
                                <span className="text-muted-foreground text-xs">
                                    ({robotsInfo.total} URL{robotsInfo.total > 1 ? "s" : ""} au total)
                                </span>
                            </div>
                            {/* Barre proportionnelle autorisées / bloquées */}
                            {robotsInfo.total > 0 && (
                                <div className="space-y-1">
                                    <Progress
                                        value={(robotsInfo.allowed / robotsInfo.total) * 100}
                                        className="h-2"
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        {Math.round((robotsInfo.allowed / robotsInfo.total) * 100)}% des URLs sont accessibles au scraping
                                    </p>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Progression du scraping en temps réel */}
                    {isIngesting && urlsTotal !== null && urlsTotal > 0 && (
                        <div className="rounded-lg border bg-indigo-50/60 p-3 space-y-2">
                            <div className="flex items-center justify-between text-sm font-medium text-indigo-800">
                                <span className="flex items-center gap-1.5">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Scraping en cours
                                </span>
                                <span>
                                    {urlsDone ?? 0} / {urlsTotal} URL{urlsTotal > 1 ? "s" : ""} scrapée{urlsTotal > 1 ? "s" : ""}
                                </span>
                            </div>
                            <Progress
                                value={urlsTotal > 0 ? ((urlsDone ?? 0) / urlsTotal) * 100 : 0}
                                className="h-2"
                            />
                        </div>
                    )}

                    {ingestMessage && <p className="text-sm text-green-600">{ingestMessage}</p>}
                    {ingestError && <p className="text-sm text-red-600">{ingestError}</p>}
                </div>

                {/* Filter Bar */}
                <div className="flex items-center gap-2 overflow-x-auto pb-2 no-scrollbar">
                    <FilterChip label="Tout" active={activeFilter === "Tout"} onClick={() => setActiveFilter("Tout")} />
                    {uniqueCategories.map(cat => (
                        <FilterChip key={cat} label={cat} active={activeFilter === cat} onClick={() => setActiveFilter(cat)} />
                    ))}
                </div>
            </div>

            <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">

                {/* Metrics Summary Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <MetricCard
                        icon={<DatabaseZap className="h-6 w-6 text-purple-500" />}
                        value={`${kbSources.length}`}
                        label="Sources indexées"
                    />
                    <MetricCard
                        icon={<Cpu className="h-6 w-6 text-indigo-500" />}
                        value={`${kbSources.reduce((s, r) => s + r.chunks, 0)}`}
                        label="Chunks IA"
                    />
                    <MetricCard
                        icon={<FileText className="h-6 w-6 text-blue-500" />}
                        value={`${uniqueCategories.length}`}
                        label="Catégories"
                    />
                </div>

                {/* Sources Grid */}
                {filteredSources.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
                        <DatabaseZap className="h-12 w-12 mb-4 opacity-30" />
                        <p className="text-base font-medium">Aucune source indexée</p>
                        <p className="text-sm mt-1">Utilisez le bouton &quot;Ajouter une source&quot; pour indexer une URL ou un fichier.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {filteredSources.map((s, i) => {
                            const isFile = !s.source.startsWith("http")
                            const ext = s.source.split(".").pop()?.toLowerCase() ?? ""
                            return (
                                <Card key={i} className="hover:shadow-md transition-shadow group">
                                    <CardContent className="p-4 flex items-start gap-3">
                                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${isFile ? "bg-indigo-50" : "bg-blue-50"}`}>
                                            {isFile
                                                ? <FileText className={`h-5 w-5 ${ext === "pdf" ? "text-red-500" : ext === "docx" ? "text-blue-600" : "text-slate-500"}`} />
                                                : <Globe className="h-5 w-5 text-blue-500" />
                                            }
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-semibold text-slate-800 truncate" title={s.source}>{s.source}</p>
                                            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                                                {s.category && <Badge variant="secondary" className="text-xs">{s.category}</Badge>}
                                                <span className="text-xs text-muted-foreground">{s.chunks} chunks</span>
                                                {s.date_creation && (
                                                    <span className="text-xs text-muted-foreground">
                                                        {new Date(s.date_creation).toLocaleDateString("fr-FR")}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive flex-shrink-0"
                                            onClick={() => setDeleteSource(s)}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </CardContent>
                                </Card>
                            )
                        })}
                    </div>
                )}
            </div>
        </div>
        <AlertDialog open={!!deleteSource} onOpenChange={(open) => { if (!open) setDeleteSource(null) }}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Supprimer cette source ?</AlertDialogTitle>
                    <AlertDialogDescription>
                        Tous les chunks indexés depuis <span className="font-medium text-foreground">{deleteSource?.source}</span> seront supprimés définitivement de la base de connaissances IA. Cette action est irréversible.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={isDeleting}>Annuler</AlertDialogCancel>
                    <AlertDialogAction
                        onClick={handleDeleteConfirm}
                        disabled={isDeleting}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                        {isDeleting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                        Supprimer
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
        </>
    )
}

function FilterChip({ label, icon, active, onClick }: { label: string, icon?: React.ReactNode, active?: boolean, onClick?: () => void }) {
    return (
        <Button
            variant={active ? "default" : "outline"}
            size="sm"
            className={`rounded-full h-8 ${active ? "" : "bg-transparent hover:bg-muted"}`}
            onClick={onClick}
        >
            {icon && <span className="mr-2 opacity-70">{icon}</span>}
            {label}
        </Button>
    )
}

function MetricCard({ icon, value, label }: { icon: React.ReactNode, value: string, label: string }) {
    return (
        <Card>
            <CardContent className="flex items-center gap-4 p-6">
                <div className="h-12 w-12 rounded-xl bg-background border flex items-center justify-center shadow-sm">
                    {icon}
                </div>
                <div>
                    <div className="text-2xl font-bold">{value}</div>
                    <div className="text-sm text-muted-foreground">{label}</div>
                </div>
            </CardContent>
        </Card>
    )
}

