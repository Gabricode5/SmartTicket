import { NextResponse } from "next/server"

const WATCHED_COMPONENTS = [
    "Chat Completions API",
    "Embeddings API",
    "Agents API",
    "Batch API",
    "Fine-tuning API",
    "Files API",
]

type ComponentStatus = {
    name: string
    status: "operational" | "degraded" | "outage" | "unknown"
    uptime: string | null
}

type StatusResponse = {
    overall: "operational" | "degraded" | "outage" | "unknown"
    components: ComponentStatus[]
    fetched_at: string
}

export async function GET() {
    try {
        const res = await fetch("https://status.mistral.ai/", {
            next: { revalidate: 60 },
            headers: { "User-Agent": "Mozilla/5.0 (compatible; SmartTicket/1.0)" },
        })

        if (!res.ok) throw new Error(`HTTP ${res.status}`)

        const html = await res.text()
        const lower = html.toLowerCase()

        // Overall status
        let overall: StatusResponse["overall"] = "operational"
        if (lower.includes("major outage")) overall = "outage"
        else if (lower.includes("partial outage") || lower.includes("degraded performance")) overall = "degraded"
        else if (lower.includes("all systems operational")) overall = "operational"

        // Components — extract uptime % and status from context
        const components: ComponentStatus[] = WATCHED_COMPONENTS.map((name) => {
            const idx = html.indexOf(name)
            if (idx === -1) return { name, status: "unknown", uptime: null }

            const context = html.substring(Math.max(0, idx - 300), idx + 300)
            const ctxLower = context.toLowerCase()

            // Status from context
            let status: ComponentStatus["status"] = "operational"
            if (ctxLower.includes("major outage") || ctxLower.includes("down")) status = "outage"
            else if (ctxLower.includes("degraded") || ctxLower.includes("partial outage")) status = "degraded"

            // Uptime % from context — pattern like "98.952%"
            const uptimeMatch = context.match(/(\d{1,3}\.\d{1,3})%/)
            const uptime = uptimeMatch ? `${uptimeMatch[1]}%` : null

            return { name, status, uptime }
        })

        const payload: StatusResponse = {
            overall,
            components,
            fetched_at: new Date().toISOString(),
        }

        return NextResponse.json(payload)
    } catch {
        return NextResponse.json({
            overall: "unknown",
            components: [],
            fetched_at: new Date().toISOString(),
        } satisfies StatusResponse)
    }
}
