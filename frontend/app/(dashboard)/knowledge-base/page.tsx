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
import { useLocale } from "@/lib/i18n/LocaleContext"

export default function KnowledgeBasePage() {
    const { messages: t, locale } = useLocale()
    const dateLocale = locale === "fr" ? "fr-FR" : "en-US"
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
                    setIngestError(t.knowledgeBase.sessionExpired)
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
                        setIngestError(t.knowledgeBase.noContentRetrieved)
                    } else {
                        const inserted = data.result?.inserted ?? "?"
                        const source = data.result?.filename ?? data.result?.url ?? sourceUrl
                        setIngestMessage(t.knowledgeBase.indexingComplete(inserted, source))
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
                    setIngestError(data.error || t.knowledgeBase.indexingError)
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
        // eslint-disable-next-line react-hooks/exhaustive-deps -- le polling ne doit pas redémarrer si la langue change en cours d'indexation
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
                setRobotsError(data?.detail || t.knowledgeBase.cannotAnalyzeSite)
                return
            }
            setRobotsInfo(await res.json())
        } catch {
            setRobotsError(t.knowledgeBase.analyzeNetworkError)
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
                    setIngestError(t.knowledgeBase.sessionExpired)
                    return
                }
                setIngestError(data?.detail || t.knowledgeBase.cannotStartIngest)
                return
            }

            if (data.status === "started") {
                isBackgroundJob = true
                setIngestMessage(data.message || t.knowledgeBase.indexingStarted)
                ingestStartedAtRef.current = Date.now()
                setIngestJobId(data.job_id || null)
                return
            }

            if (data.inserted === 0) {
                setIngestError(t.knowledgeBase.noContentRetrieved)
                return
            }
            setIngestMessage(t.knowledgeBase.contentsIndexed(data.inserted, data.url))
        } catch (error) {
            console.error("Erreur ingestion URL:", error)
            setIngestError(t.knowledgeBase.ingestNetworkError)
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
            setUploadError(t.knowledgeBase.selectFileError)
            return
        }
        const ext = selectedFile.name.split(".").pop()?.toLowerCase()
        if (ext !== "docx" && ext !== "txt" && ext !== "pdf") {
            setUploadError(t.knowledgeBase.fileTypeError)
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
                setUploadError(data?.detail || t.knowledgeBase.uploadError)
                setIsUploadingFile(false)
                return
            }
            if (data.status === "started") {
                setIngestMessage(data.message || t.knowledgeBase.fileIndexingStarted)
                ingestStartedAtRef.current = Date.now()
                setIngestJobId(data.job_id || null)
                setIsAddDialogOpen(false)
                setNewArticle({ title: "", category: "Guides", summary: "", tags: "", fileName: "" })
                setSelectedFile(null)
            }
        } catch {
            setUploadError(t.knowledgeBase.uploadNetworkError)
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
                    <h1 className="text-2xl font-bold tracking-tight">{t.knowledgeBase.title}</h1>
                    <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
                        <DialogTrigger asChild>
                            <Button>
                                <Plus className="mr-2 h-4 w-4" />
                                {t.knowledgeBase.addArticle}
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[500px]">
                            <DialogHeader>
                                <DialogTitle>{t.knowledgeBase.addDialogTitle}</DialogTitle>
                                <DialogDescription>
                                    {t.knowledgeBase.addDialogDesc}
                                </DialogDescription>
                            </DialogHeader>

                            <div className="grid gap-4 py-4">
                                <div className="grid gap-2">
                                    <Label htmlFor="title">{t.knowledgeBase.titleLabel}</Label>
                                    <Input
                                        id="title"
                                        value={newArticle.title}
                                        onChange={(e) => setNewArticle({ ...newArticle, title: e.target.value })}
                                        placeholder={t.knowledgeBase.titlePlaceholder}
                                    />
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="category">{t.knowledgeBase.categoryLabel}</Label>
                                    <Select
                                        value={newArticle.category}
                                        onValueChange={(value) => setNewArticle({ ...newArticle, category: value })}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder={t.knowledgeBase.categoryPlaceholder} />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="FAQ">{t.knowledgeBase.categoryFaq}</SelectItem>
                                            <SelectItem value="Guides">{t.knowledgeBase.categoryGuides}</SelectItem>
                                            <SelectItem value="Documentation">{t.knowledgeBase.categoryDocumentation}</SelectItem>
                                            <SelectItem value="Formés IA">{t.knowledgeBase.categoryAiTrained}</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="tags">{t.knowledgeBase.tagsLabel}</Label>
                                    <Input
                                        id="tags"
                                        value={newArticle.tags}
                                        onChange={(e) => setNewArticle({ ...newArticle, tags: e.target.value })}
                                        placeholder={t.knowledgeBase.tagsPlaceholder}
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
                                            {newArticle.fileName ? newArticle.fileName : t.knowledgeBase.clickToImport}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">
                                            {t.knowledgeBase.fileHint}
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
                                    {isUploadingFile ? t.knowledgeBase.sending : t.knowledgeBase.importAndIndex}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>

                <div className="relative">
                    <Search className="absolute left-3.5 top-3.5 h-5 w-5 text-muted-foreground" />
                    <Input
                        placeholder={t.knowledgeBase.searchPlaceholder}
                        className="pl-12 h-12 text-lg rounded-xl bg-muted/30 border-muted-foreground/20 focus-visible:bg-background"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <div className="rounded-xl border bg-card p-4 space-y-3">
                    <Label htmlFor="source-url">{t.knowledgeBase.indexUrlLabel}</Label>
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
                            {isCheckingRobots ? t.knowledgeBase.checkingRobots : t.knowledgeBase.checkRobots}
                        </Button>
                        <Button onClick={handleIngestUrl} disabled={isIngesting || !sourceUrl.trim()}>
                            {isIngesting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            {isIngesting ? t.knowledgeBase.indexing : t.knowledgeBase.indexUrl}
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
                                <span className="flex items-center gap-1.5 font-medium text-foreground">
                                    <LinkIcon className="h-4 w-4 text-muted-foreground" />
                                    {robotsInfo.sitemap_found ? t.knowledgeBase.sitemapFound : t.knowledgeBase.noSitemap}
                                    {!robotsInfo.robots_found && <span className="text-xs text-muted-foreground ml-1">{t.knowledgeBase.robotsAbsent}</span>}
                                </span>
                                <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                                    <ShieldCheck className="h-4 w-4" />
                                    {t.knowledgeBase.urlsAllowed(robotsInfo.allowed)}
                                </span>
                                {robotsInfo.blocked > 0 && (
                                    <span className="flex items-center gap-1 text-red-600 font-semibold">
                                        <ShieldAlert className="h-4 w-4" />
                                        {t.knowledgeBase.urlsBlocked(robotsInfo.blocked)}
                                    </span>
                                )}
                                <span className="text-muted-foreground text-xs">
                                    {t.knowledgeBase.urlsTotal(robotsInfo.total)}
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
                                        {t.knowledgeBase.scrapableRate(Math.round((robotsInfo.allowed / robotsInfo.total) * 100))}
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
                                    {t.knowledgeBase.scrapingInProgress}
                                </span>
                                <span>
                                    {t.knowledgeBase.scrapedProgress(urlsDone ?? 0, urlsTotal)}
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
                    <FilterChip label={t.knowledgeBase.filterAll} active={activeFilter === "Tout"} onClick={() => setActiveFilter("Tout")} />
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
                        label={t.knowledgeBase.sourcesIndexed}
                    />
                    <MetricCard
                        icon={<Cpu className="h-6 w-6 text-indigo-500" />}
                        value={`${kbSources.reduce((s, r) => s + r.chunks, 0)}`}
                        label={t.knowledgeBase.aiChunks}
                    />
                    <MetricCard
                        icon={<FileText className="h-6 w-6 text-blue-500" />}
                        value={`${uniqueCategories.length}`}
                        label={t.knowledgeBase.categories}
                    />
                </div>

                {/* Sources Grid */}
                {filteredSources.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
                        <DatabaseZap className="h-12 w-12 mb-4 opacity-30" />
                        <p className="text-base font-medium">{t.knowledgeBase.noSourceIndexed}</p>
                        <p className="text-sm mt-1">{t.knowledgeBase.noSourceHint}</p>
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
                                                ? <FileText className={`h-5 w-5 ${ext === "pdf" ? "text-red-500" : ext === "docx" ? "text-blue-600" : "text-muted-foreground"}`} />
                                                : <Globe className="h-5 w-5 text-blue-500" />
                                            }
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-semibold text-foreground truncate" title={s.source}>{s.source}</p>
                                            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                                                {s.category && <Badge variant="secondary" className="text-xs">{s.category}</Badge>}
                                                <span className="text-xs text-muted-foreground">{t.knowledgeBase.chunksLabel(s.chunks)}</span>
                                                {s.date_creation && (
                                                    <span className="text-xs text-muted-foreground">
                                                        {new Date(s.date_creation).toLocaleDateString(dateLocale)}
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
                    <AlertDialogTitle>{t.knowledgeBase.deleteSourceTitle}</AlertDialogTitle>
                    <AlertDialogDescription>
                        {t.knowledgeBase.deleteSourceIntro} <span className="font-medium text-foreground">{deleteSource?.source}</span> {t.knowledgeBase.deleteSourceOutro}
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={isDeleting}>{t.knowledgeBase.cancel}</AlertDialogCancel>
                    <AlertDialogAction
                        onClick={handleDeleteConfirm}
                        disabled={isDeleting}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                        {isDeleting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                        {t.knowledgeBase.delete}
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

