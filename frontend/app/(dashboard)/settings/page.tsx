"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Download, Compass } from "lucide-react"
import { onboardingStorageKey } from "@/components/onboarding/OnboardingModal"
import { ThemeToggle } from "@/components/ThemeToggle"
import { LanguageToggle } from "@/components/LanguageToggle"
import { useLocale } from "@/lib/i18n/LocaleContext"

type Me = {
    id: number
    username: string
    email: string
    prenom?: string | null
    nom?: string | null
    role: string
    email_verified: boolean
    date_creation: string
}

export default function SettingsPage() {
    const router = useRouter()
    const { messages: t } = useLocale()
    const [loading, setLoading] = useState(true)
    const [savingProfile, setSavingProfile] = useState(false)
    const [savingPassword, setSavingPassword] = useState(false)
    const [exporting, setExporting] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const [account, setAccount] = useState<{ id: number; role: string } | null>(null)
    const [emailVerified, setEmailVerified] = useState(true)
    const [resendingVerification, setResendingVerification] = useState(false)
    const [verificationResent, setVerificationResent] = useState(false)

    const [profile, setProfile] = useState({
        username: "",
        email: "",
        prenom: "",
        nom: "",
    })

    const [passwordForm, setPasswordForm] = useState({
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
    })

    useEffect(() => {
        const loadMe = async () => {
            setError(null)
            setSuccess(null)

            try {
                const response = await fetch("/api/me")
                if (!response.ok) {
                    if (response.status === 401) {
                        setError(t.settings.sessionExpired)
                        setLoading(false)
                        return
                    }
                    setError(t.settings.loadProfileError)
                    setLoading(false)
                    return
                }

                const me: Me = await response.json()
                setProfile({
                    username: me.username || "",
                    email: me.email || "",
                    prenom: me.prenom || "",
                    nom: me.nom || "",
                })
                setAccount({ id: me.id, role: me.role })
                setEmailVerified(me.email_verified)
            } catch (e) {
                console.error("Erreur chargement profil:", e)
                setError(t.settings.networkError)
            } finally {
                setLoading(false)
            }
        }

        loadMe()
        // eslint-disable-next-line react-hooks/exhaustive-deps -- chargement initial du profil, ne doit pas se relancer au changement de langue
    }, [])

    const handleSaveProfile = async () => {
        setError(null)
        setSuccess(null)

        setSavingProfile(true)
        try {
            const response = await fetch("/api/me", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    username: profile.username,
                    email: profile.email,
                    prenom: profile.prenom,
                    nom: profile.nom,
                }),
            })

            const data = await response.json()
            if (!response.ok) {
                if (response.status === 401) {
                    setError(t.settings.sessionExpired)
                    return
                }
                setError(data?.detail || t.settings.saveProfileError)
                return
            }

            localStorage.setItem("username", data.username)
            localStorage.setItem("user_email", data.email)
            setEmailVerified(data.email_verified)
            setVerificationResent(false)
            setSuccess(t.settings.profileUpdated)
        } catch (e) {
            console.error("Erreur sauvegarde profil:", e)
            setError(t.settings.networkError)
        } finally {
            setSavingProfile(false)
        }
    }

    const handleExportData = async () => {
        setExporting(true)
        setError(null)
        try {
            const response = await fetch("/api/me/export")
            if (!response.ok) {
                setError(t.settings.exportError)
                return
            }
            const blob = await response.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = `mes-donnees-smartticket-${new Date().toISOString().slice(0, 10)}.pdf`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            URL.revokeObjectURL(url)
        } catch {
            setError(t.settings.networkError)
        } finally {
            setExporting(false)
        }
    }

    const handleResendVerification = async () => {
        setResendingVerification(true)
        try {
            await fetch("/api/resend-verification", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: profile.email }),
            })
        } finally {
            setVerificationResent(true)
            setResendingVerification(false)
        }
    }

    const handleReplayOnboarding = () => {
        if (!account) return
        window.localStorage.removeItem(onboardingStorageKey(account.id, account.role))
        router.push("/dashboard")
    }

    const handleSavePassword = async () => {
        setError(null)
        setSuccess(null)

        if (!passwordForm.currentPassword || !passwordForm.newPassword) {
            setError(t.settings.passwordFieldsRequired)
            return
        }
        if (passwordForm.newPassword !== passwordForm.confirmPassword) {
            setError(t.settings.passwordMismatch)
            return
        }

        setSavingPassword(true)
        try {
            const response = await fetch("/api/me/password", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    current_password: passwordForm.currentPassword,
                    new_password: passwordForm.newPassword,
                }),
            })

            const data = await response.json()
            if (!response.ok) {
                if (response.status === 401) {
                    setError(t.settings.sessionExpired)
                    return
                }
                setError(data?.detail || t.settings.passwordUpdateError)
                return
            }

            setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" })
            setSuccess(t.settings.passwordUpdated)
        } catch (e) {
            console.error("Erreur mot de passe:", e)
            setError(t.settings.networkError)
        } finally {
            setSavingPassword(false)
        }
    }

    return (
        <div className="flex flex-col min-h-full p-8 space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">{t.settings.title}</h1>
                <p className="text-sm text-muted-foreground mt-1">{t.settings.subtitle}</p>
            </div>

            {error && <div className="rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-3 py-2 text-sm text-red-600 dark:text-red-400">{error}</div>}
            {success && <div className="rounded-md border border-green-200 dark:border-green-900 bg-green-50 dark:bg-green-950/30 px-3 py-2 text-sm text-green-700 dark:text-green-400">{success}</div>}
            {!loading && !emailVerified && (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 flex flex-wrap items-center justify-between gap-2">
                    <span>{t.settings.verifyEmailBanner}</span>
                    {verificationResent ? (
                        <span className="text-xs font-medium">{t.settings.emailResent}</span>
                    ) : (
                        <button
                            type="button"
                            onClick={handleResendVerification}
                            disabled={resendingVerification}
                            className="text-xs font-semibold underline underline-offset-2 disabled:opacity-60"
                        >
                            {resendingVerification ? t.settings.resending : t.settings.resendEmail}
                        </button>
                    )}
                </div>
            )}

            <Card>
                <CardHeader>
                    <CardTitle>{t.settings.profileTitle}</CardTitle>
                    <CardDescription>{t.settings.profileDesc}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-2">
                        <Label htmlFor="username">{t.settings.usernameLabel}</Label>
                        <Input
                            id="username"
                            value={profile.username}
                            disabled={loading}
                            onChange={(e) => setProfile({ ...profile, username: e.target.value })}
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="email">{t.settings.emailLabel}</Label>
                        <Input
                            id="email"
                            type="email"
                            value={profile.email}
                            disabled={loading}
                            onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                        />
                    </div>
                    <div className="grid gap-2 md:grid-cols-2">
                        <div className="grid gap-2">
                            <Label htmlFor="prenom">{t.settings.firstNameLabel}</Label>
                            <Input
                                id="prenom"
                                value={profile.prenom}
                                disabled={loading}
                                onChange={(e) => setProfile({ ...profile, prenom: e.target.value })}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="nom">{t.settings.lastNameLabel}</Label>
                            <Input
                                id="nom"
                                value={profile.nom}
                                disabled={loading}
                                onChange={(e) => setProfile({ ...profile, nom: e.target.value })}
                            />
                        </div>
                    </div>
                    <Button onClick={handleSaveProfile} disabled={loading || savingProfile}>
                        {savingProfile ? t.settings.savingProfile : t.settings.saveProfile}
                    </Button>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>{t.settings.passwordTitle}</CardTitle>
                    <CardDescription>{t.settings.passwordDesc}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-2">
                        <Label htmlFor="currentPassword">{t.settings.currentPasswordLabel}</Label>
                        <Input
                            id="currentPassword"
                            type="password"
                            value={passwordForm.currentPassword}
                            onChange={(e) => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="newPassword">{t.settings.newPasswordLabel}</Label>
                        <Input
                            id="newPassword"
                            type="password"
                            value={passwordForm.newPassword}
                            onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="confirmPassword">{t.settings.confirmPasswordLabel}</Label>
                        <Input
                            id="confirmPassword"
                            type="password"
                            value={passwordForm.confirmPassword}
                            onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                        />
                    </div>
                    <Button onClick={handleSavePassword} disabled={savingPassword}>
                        {savingPassword ? t.settings.updatingPassword : t.settings.updatePassword}
                    </Button>
                </CardContent>
            </Card>
            <Card>
                <CardHeader>
                    <CardTitle>{t.settings.appearanceTitle}</CardTitle>
                    <CardDescription>{t.settings.appearanceDesc}</CardDescription>
                </CardHeader>
                <CardContent>
                    <ThemeToggle />
                </CardContent>
            </Card>
            <Card>
                <CardHeader>
                    <CardTitle>{t.settings.languageTitle}</CardTitle>
                    <CardDescription>{t.settings.languageDesc}</CardDescription>
                </CardHeader>
                <CardContent>
                    <LanguageToggle />
                </CardContent>
            </Card>
            <Card>
                <CardHeader>
                    <CardTitle>{t.settings.dataTitle}</CardTitle>
                    <CardDescription>
                        {t.settings.dataDesc}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                        {t.settings.dataBody}
                    </p>
                    <Button variant="outline" onClick={handleExportData} disabled={exporting}>
                        <Download className="mr-2 h-4 w-4" />
                        {exporting ? t.settings.preparingExport : t.settings.downloadData}
                    </Button>
                </CardContent>
            </Card>
            <Card>
                <CardHeader>
                    <CardTitle>{t.settings.helpTitle}</CardTitle>
                    <CardDescription>
                        {t.settings.helpDesc}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Button variant="outline" onClick={handleReplayOnboarding} disabled={!account}>
                        <Compass className="mr-2 h-4 w-4" />
                        {t.settings.replayOnboarding}
                    </Button>
                </CardContent>
            </Card>
        </div>
    )
}
