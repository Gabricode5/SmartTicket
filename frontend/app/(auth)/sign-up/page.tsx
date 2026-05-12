"use client" //pour utiliser les formulaires et le state

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation" //pour la navigation après l'inscription
import { Button } from "@/components/ui/button"
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function SignUpPage() {

    const router = useRouter()
    const [error, setError] = useState("")
    const [rgpdAccepted, setRgpdAccepted] = useState(false)

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault() // Empêche le rechargement de la page
        setError("")

        if (!rgpdAccepted) {
            setError("Vous devez accepter la politique de confidentialité pour créer un compte.")
            return
        }

        const formData = new FormData(event.currentTarget)
        const data = Object.fromEntries(formData)

        // On prépare l'objet exactement comme ton backend l'attend (UserCreate)
        const payload = {
            username: data.username,
            email: data.email,
            password: data.password,
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
                // Inscription réussie ! On redirige vers le login
                router.push("/login")
            } else {
                // 1. On récupère le JSON d'erreur (ex: { "detail": "Cet email est déjà utilisé." })
                const errorData = await response.json()
                // 2. On met à jour le state 'error' avec le message précis du backend
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
                    <div className="space-y-2">
                        <Label htmlFor="password">Mot de passe</Label>
                        <Input id="password" name="password" type="password" required />
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
                    <Button type="submit" className="w-full" disabled={!rgpdAccepted}>
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
