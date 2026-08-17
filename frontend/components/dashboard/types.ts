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

export type SessionSearchResult = {
    id: number
    title?: string | null
    date_creation?: string | null
    status?: string | null
    snippet?: string | null
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

export type Ticket = {
    id: number
    ticket_number: number
    session_id: number
    status: "new" | "in_progress" | "resolved" | "closed"
    waiting_on: "us" | "customer"
    assigned_agent_id?: number | null
    priority: "normal" | "urgent"
    reason?: string | null
    context_cutoff_message_id?: number | null
    created_at: string
    updated_at: string
    client_username?: string | null
    client_email?: string | null
    assigned_agent_username?: string | null
}

export type TicketListResponse = {
    items: Ticket[]
    total: number
    page: number
    page_size: number
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
