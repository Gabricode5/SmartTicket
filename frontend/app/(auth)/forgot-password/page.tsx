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
import { ArrowLeft } from "lucide-react"

export default function ForgotPasswordPage() {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-2xl">Mot de passe oublié ?</CardTitle>
                <CardDescription>
                    Entrez votre email pour réinitialiser votre mot de passe.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" type="email" placeholder="m@exemple.com" required />
                </div>
                <Button type="submit" className="w-full">
                    Envoyer le lien
                </Button>
            </CardContent>
            <CardFooter className="flex justify-center">
                <Link
                    href="/login"
                    className="flex items-center text-sm text-muted-foreground underline-offset-4 hover:underline"
                >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Retour à la connexion
                </Link>
            </CardFooter>
        </Card>
    )
}
