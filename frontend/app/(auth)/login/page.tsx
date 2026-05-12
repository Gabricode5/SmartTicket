"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
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

export default function LoginPage() {
    return <LoginForm />
}

function LoginForm() {
    const router = useRouter()
    const [error, setError] = useState("")

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")

    const formData = new FormData(event.currentTarget)
    const email = formData.get("email")
    const password = formData.get("password")

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        })

        const data = await response.json()

        if (response.ok) {
            // Le backend pose le cookie HttpOnly. On garde seulement les infos d'affichage.
            localStorage.setItem("username", data.username)
            localStorage.setItem("user_email", email as string)
            localStorage.setItem("user_role", data.nom_role)
            localStorage.setItem("user_id", data.user_id)

            // 2. Redirection vers le dashboard ou l'accueil
            router.push("/")
            router.refresh() // Pour mettre à jour les composants layout
        } else {
            // Afficher le message d'erreur du backend (ex: "L'email ou le mot de passe est incorrect")
            setError(data.detail || "Échec de la connexion")
        }
        } catch {
            setError("Impossible de contacter le serveur.")
        }
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-2xl">Connexion</CardTitle>
                <CardDescription>
                    Entrez vos identifiants pour accéder à votre compte.
                </CardDescription>
            </CardHeader>
            <form onSubmit={handleSubmit}>
                <CardContent className="space-y-4">
                    {error && (
                        <div className="p-3 text-sm text-red-500 bg-red-50 rounded-md">
                            {error}
                        </div>
                    )}
                    <div className="space-y-2">
                        <Label htmlFor="email">Email</Label>
                        <Input
                            id="email"
                            name="email"
                            type="email"
                            placeholder="mail@exemple.com"
                            required
                        />
                    </div>
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="password">Mot de passe</Label>
                            <Link
                                href="/forgot-password"
                                className="text-sm text-muted-foreground underline-offset-4 hover:underline"
                            >
                                Mot de passe oublié ?
                            </Link>
                        </div>
                        <Input
                            id="password"
                            name="password"
                            type="password"
                            required
                        />
                    </div>
                    <Button type="submit" className="w-full">
                        Se connecter
                    </Button>
                </CardContent>
            </form>
            <CardFooter className="flex justify-center">
                <div className="text-sm text-muted-foreground">
                    Pas encore de compte ?{" "}
                    <Link href="/sign-up" className="underline underline-offset-4 hover:text-primary">
                        S&apos;inscrire
                    </Link>
                </div>
            </CardFooter>
        </Card>
    )
}
