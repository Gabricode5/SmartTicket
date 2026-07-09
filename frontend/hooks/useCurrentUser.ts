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
