"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"

type GuestSessionResponse = {
    session?: { id?: number }
}

export default function StartChatPage() {
    const router = useRouter()
    const [error, setError] = useState("")
    const startedRef = useRef(false)

    useEffect(() => {
        // StrictMode monte les effets deux fois en dev — sans cette garde, on créerait
        // deux comptes invités (et deux sessions) pour une seule visite.
        if (startedRef.current) return
        startedRef.current = true

        fetch("/api/sessions/guest", { method: "POST" })
            .then(async (response) => {
                if (!response.ok) {
                    setError("Impossible de démarrer la conversation pour le moment.")
                    return
                }
                const data: GuestSessionResponse = await response.json()
                if (!data.session?.id) {
                    setError("Impossible de démarrer la conversation pour le moment.")
                    return
                }
                router.replace(`/ai-assistant/${data.session.id}`)
            })
            .catch(() => setError("Impossible de contacter le serveur."))
    }, [router])

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/40 to-white flex flex-col items-center justify-center px-4">
            {error ? (
                <div className="text-center space-y-4">
                    <p className="text-sm text-red-600">{error}</p>
                    <Link href="/" className="inline-flex items-center gap-2 text-sm text-indigo-600 hover:underline">
                        <ArrowLeft className="h-4 w-4" />
                        Retour à l&apos;accueil
                    </Link>
                </div>
            ) : (
                <div className="flex flex-col items-center gap-3 text-slate-500 text-sm">
                    <div className="h-8 w-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
                    Démarrage de la conversation…
                </div>
            )}
        </div>
    )
}
