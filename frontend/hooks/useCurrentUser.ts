"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

export type CurrentUser = {
    id: number
    username: string
    email: string
    prenom?: string | null
    nom?: string | null
    role: string
    is_guest?: boolean
    // Système de pôles (feature/poles) : poles_enabled reflète POLES_ENABLED côté backend
    // (false sur une instance qui n'utilise pas la feature — tout ce qui en dépend doit
    // rester caché). pole_id/pole_nom sont absents pour l'admin et un superviseur qui
    // n'est pas devenu manager (ni bug ni donnée manquante : ces rôles n'ont légitimement
    // pas de pôle). managed_poles est non-vide seulement pour un manager (superviseur avec
    // des pôles assignés) — objets complets (pas juste des ids) car un manager n'a pas
    // accès à GET /poles (réservé au super admin), /me est sa seule source pour ces noms.
    poles_enabled?: boolean
    pole_id?: number | null
    pole_nom?: string | null
    managed_poles?: { id: number; nom: string; is_global: boolean }[]
}

export function useCurrentUser() {
    const router = useRouter()
    const [user, setUser] = useState<CurrentUser | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        fetch("/api/me")
            .then((res) => {
                if (res.status === 401) { router.replace("/login"); return null }
                return res.ok ? res.json() : null
            })
            .then((data) => { if (data) setUser(data) })
            .catch(() => {})
            .finally(() => setIsLoading(false))
    }, [router])

    return { user, isLoading }
}
