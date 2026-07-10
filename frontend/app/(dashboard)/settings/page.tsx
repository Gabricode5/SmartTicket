"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Download, Compass } from "lucide-react"
import { onboardingStorageKey } from "@/components/onboarding/OnboardingModal"

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
                        setError("Session expirée. Veuillez vous reconnecter.")
                        setLoading(false)
                        return
                    }
                    setError("Impossible de charger votre profil.")
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
                setError("Erreur réseau.")
            } finally {
                setLoading(false)
            }
        }

        loadMe()
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
                    setError("Session expirée. Veuillez vous reconnecter.")
                    return
                }
                setError(data?.detail || "Impossible de sauvegarder le profil.")
                return
            }

            localStorage.setItem("username", data.username)
            localStorage.setItem("user_email", data.email)
            setEmailVerified(data.email_verified)
            setVerificationResent(false)
            setSuccess("Profil mis à jour.")
        } catch (e) {
            console.error("Erreur sauvegarde profil:", e)
            setError("Erreur réseau.")
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
                setError("Impossible d'exporter vos données.")
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
            setError("Erreur réseau.")
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
            setError("Veuillez remplir les champs mot de passe.")
            return
        }
        if (passwordForm.newPassword !== passwordForm.confirmPassword) {
            setError("La confirmation du nouveau mot de passe ne correspond pas.")
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
                    setError("Session expirée. Veuillez vous reconnecter.")
                    return
                }
                setError(data?.detail || "Impossible de modifier le mot de passe.")
                return
            }

            setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" })
            setSuccess("Mot de passe mis à jour.")
        } catch (e) {
            console.error("Erreur mot de passe:", e)
            setError("Erreur réseau.")
        } finally {
            setSavingPassword(false)
        }
    }

    return (
        <div className="flex flex-col min-h-full p-8 space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Paramètres du compte</h1>
                <p className="text-sm text-muted-foreground mt-1">Modifiez vos informations personnelles et votre mot de passe.</p>
            </div>

            {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            {success && <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{success}</div>}
            {!loading && !emailVerified && (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 flex flex-wrap items-center justify-between gap-2">
                    <span>Confirmez votre nouvelle adresse email — un lien de confirmation vous a été envoyé.</span>
                    {verificationResent ? (
                        <span className="text-xs font-medium">Email renvoyé.</span>
                    ) : (
                        <button
                            type="button"
                            onClick={handleResendVerification}
                            disabled={resendingVerification}
                            className="text-xs font-semibold underline underline-offset-2 disabled:opacity-60"
                        >
                            {resendingVerification ? "Envoi…" : "Renvoyer l'email"}
                        </button>
                    )}
                </div>
            )}

            <Card>
                <CardHeader>
                    <CardTitle>Profil</CardTitle>
                    <CardDescription>Informations de base du compte.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-2">
                        <Label htmlFor="username">Nom d&apos;utilisateur</Label>
                        <Input
                            id="username"
                            value={profile.username}
                            disabled={loading}
                            onChange={(e) => setProfile({ ...profile, username: e.target.value })}
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="email">Email</Label>
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
                            <Label htmlFor="prenom">Prénom</Label>
                            <Input
                                id="prenom"
                                value={profile.prenom}
                                disabled={loading}
                                onChange={(e) => setProfile({ ...profile, prenom: e.target.value })}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="nom">Nom</Label>
                            <Input
                                id="nom"
                                value={profile.nom}
                                disabled={loading}
                                onChange={(e) => setProfile({ ...profile, nom: e.target.value })}
                            />
                        </div>
                    </div>
                    <Button onClick={handleSaveProfile} disabled={loading || savingProfile}>
                        {savingProfile ? "Enregistrement..." : "Enregistrer le profil"}
                    </Button>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Mot de passe</CardTitle>
                    <CardDescription>Changez votre mot de passe.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-2">
                        <Label htmlFor="currentPassword">Mot de passe actuel</Label>
                        <Input
                            id="currentPassword"
                            type="password"
                            value={passwordForm.currentPassword}
                            onChange={(e) => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="newPassword">Nouveau mot de passe</Label>
                        <Input
                            id="newPassword"
                            type="password"
                            value={passwordForm.newPassword}
                            onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="confirmPassword">Confirmer le nouveau mot de passe</Label>
                        <Input
                            id="confirmPassword"
                            type="password"
                            value={passwordForm.confirmPassword}
                            onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                        />
                    </div>
                    <Button onClick={handleSavePassword} disabled={savingPassword}>
                        {savingPassword ? "Mise à jour..." : "Mettre à jour le mot de passe"}
                    </Button>
                </CardContent>
            </Card>
            <Card>
                <CardHeader>
                    <CardTitle>Mes données personnelles</CardTitle>
                    <CardDescription>
                        Conformément au RGPD (Art. 15 et 20), vous pouvez télécharger l&apos;intégralité de vos données.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                        Le fichier PDF contient votre profil, toutes vos conversations et l&apos;ensemble des messages échangés.
                    </p>
                    <Button variant="outline" onClick={handleExportData} disabled={exporting}>
                        <Download className="mr-2 h-4 w-4" />
                        {exporting ? "Préparation..." : "Télécharger mes données"}
                    </Button>
                </CardContent>
            </Card>
            <Card>
                <CardHeader>
                    <CardTitle>Aide</CardTitle>
                    <CardDescription>
                        Revoir la présentation guidée de l&apos;application pour votre rôle.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Button variant="outline" onClick={handleReplayOnboarding} disabled={!account}>
                        <Compass className="mr-2 h-4 w-4" />
                        Revoir la visite guidée
                    </Button>
                </CardContent>
            </Card>
        </div>
    )
}
