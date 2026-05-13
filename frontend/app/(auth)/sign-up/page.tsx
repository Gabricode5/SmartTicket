"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Eye, EyeOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type Strength = { score: number; label: string; color: string; textColor: string }

function getStrength(password: string): Strength {
    if (!password) return { score: 0, label: "", color: "", textColor: "" }
    let score = 0
    if (password.length >= 6) score++
    if (password.length >= 10) score++
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++
    if (/[0-9]/.test(password)) score++
    if (/[^A-Za-z0-9]/.test(password)) score++

    if (score <= 1) return { score: 1, label: "Très faible", color: "bg-red-500", textColor: "text-red-500" }
    if (score === 2) return { score: 2, label: "Faible", color: "bg-orange-500", textColor: "text-orange-500" }
    if (score === 3) return { score: 3, label: "Moyen", color: "bg-yellow-500", textColor: "text-yellow-600" }
    if (score === 4) return { score: 4, label: "Fort", color: "bg-green-500", textColor: "text-green-600" }
    return { score: 5, label: "Très fort", color: "bg-emerald-600", textColor: "text-emerald-600" }
}

export default function SignUpPage() {
    const router = useRouter()
    const [error, setError] = useState("")
    const [rgpdAccepted, setRgpdAccepted] = useState(false)
    const [password, setPassword] = useState("")
    const [confirmPassword, setConfirmPassword] = useState("")
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirm, setShowConfirm] = useState(false)

    const strength = getStrength(password)
    const passwordsMatch = confirmPassword === "" || password === confirmPassword
    const canSubmit = rgpdAccepted && password.length >= 6 && password === confirmPassword

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setError("")

        if (!rgpdAccepted) {
            setError("Vous devez accepter la politique de confidentialité pour créer un compte.")
            return
        }
        if (password.length < 6) {
            setError("Le mot de passe doit contenir au moins 6 caractères.")
            return
        }
        if (password !== confirmPassword) {
            setError("Les mots de passe ne correspondent pas.")
            return
        }

        const formData = new FormData(event.currentTarget)
        const data = Object.fromEntries(formData)

        const payload = {
            username: data.username,
            email: data.email,
            password,
            prenom: data.prenom,
            nom: data.nom,
        }

        try {
            const response = await fetch("/api/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })

            if (response.ok) {
                router.push("/login")
            } else {
                const errorData = await response.json()
                setError(errorData.detail || "Une erreur est survenue")
            }
        } catch {
            setError("Impossible de contacter le serveur.")
        }
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-2xl">Créer un compte</CardTitle>
                <CardDescription>
                    Entrez vos informations pour créer votre compte.
                </CardDescription>
            </CardHeader>
            <form onSubmit={handleSubmit}>
                <CardContent className="space-y-4">
                    {error && (
                        <div className="p-3 text-sm font-medium text-destructive bg-destructive/10 border border-destructive/20 rounded-md">
                            {error}
                        </div>
                    )}
                    <div className="space-y-2">
                        <Label htmlFor="username">Nom d&apos;utilisateur</Label>
                        <Input id="username" name="username" placeholder="nom_d_utilisateur" required />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="email">Email</Label>
                        <Input id="email" name="email" type="email" placeholder="email@exemple.com" required />
                    </div>

                    {/* Mot de passe */}
                    <div className="space-y-2">
                        <Label htmlFor="password">Mot de passe</Label>
                        <div className="relative">
                            <Input
                                id="password"
                                name="password"
                                type={showPassword ? "text" : "password"}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="pr-10"
                                required
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword((v) => !v)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                tabIndex={-1}
                            >
                                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>

                        {/* Indicateur de robustesse */}
                        {password && (
                            <div className="space-y-1.5">
                                <div className="flex gap-1">
                                    {[1, 2, 3, 4, 5].map((i) => (
                                        <div
                                            key={i}
                                            className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
                                                i <= strength.score ? strength.color : "bg-muted"
                                            }`}
                                        />
                                    ))}
                                </div>
                                <p className={`text-xs font-medium ${strength.textColor}`}>
                                    {strength.label}
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Confirmation mot de passe */}
                    <div className="space-y-2">
                        <Label htmlFor="confirmPassword">Confirmer le mot de passe</Label>
                        <div className="relative">
                            <Input
                                id="confirmPassword"
                                type={showConfirm ? "text" : "password"}
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                className={`pr-10 ${!passwordsMatch ? "border-destructive focus-visible:ring-destructive" : ""}`}
                                required
                            />
                            <button
                                type="button"
                                onClick={() => setShowConfirm((v) => !v)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                tabIndex={-1}
                            >
                                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                        {!passwordsMatch && (
                            <p className="text-xs text-destructive">Les mots de passe ne correspondent pas.</p>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="prenom">Prénom</Label>
                        <Input id="prenom" name="prenom" placeholder="Jean" required />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="name">Nom</Label>
                        <Input id="name" name="nom" placeholder="Dupont" required />
                    </div>
                    <div className="flex items-start gap-3 pt-2">
                        <input
                            id="rgpd"
                            type="checkbox"
                            checked={rgpdAccepted}
                            onChange={(e) => setRgpdAccepted(e.target.checked)}
                            className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
                        />
                        <Label htmlFor="rgpd" className="text-sm font-normal leading-snug cursor-pointer">
                            J&apos;accepte que mes données personnelles (nom, email) soient
                            traitées afin de gérer mon compte, conformément au{" "}
                            <a href="https://www.cnil.fr/fr/rgpd-de-quoi-parle-t-on" target="_blank" rel="noopener noreferrer" className="underline underline-offset-4 hover:text-primary">
                                RGPD
                            </a>
                            . Elles ne seront pas transmises à des tiers.
                        </Label>
                    </div>
                    <Button type="submit" className="w-full" disabled={!canSubmit}>
                        S&apos;inscrire
                    </Button>
                </CardContent>
            </form>
            <CardFooter className="flex justify-center">
                <div className="text-sm text-muted-foreground">
                    Déjà un compte ?{" "}
                    <Link href="/login" className="underline underline-offset-4 hover:text-primary">
                        Se connecter
                    </Link>
                </div>
            </CardFooter>
        </Card>
    )
}
