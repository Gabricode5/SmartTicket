export type UserItem = {
    id: number
    username: string
    email: string
    prenom?: string | null
    nom?: string | null
    role: string
}

export type SessionItem = {
    id: number
    title?: string | null
    date_creation?: string | null
    status?: string | null
    has_sav_reply?: boolean
}

export type TransferredSession = {
    id: number
    title?: string | null
    status: string
    transfer_reason?: string | null
    date_creation?: string | null
    username: string
}

export type MessageItem = {
    id: string
    role: "user" | "ai" | "sav"
    content: string
    createdAt: string
}

export const REASON_STYLES: Record<string, string> = {
    technique: "bg-sky-100 text-sky-700 border-sky-200",
    complexe:  "bg-amber-100 text-amber-700 border-amber-200",
    sensible:  "bg-red-100 text-red-700 border-red-200",
    autre:     "bg-violet-100 text-violet-700 border-violet-200",
}

export const REASON_LABELS: Record<string, string> = {
    technique: "Technique",
    complexe:  "Complexe",
    sensible:  "Sensible",
    autre:     "Autre",
}
