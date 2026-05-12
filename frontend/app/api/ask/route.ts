import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const question = searchParams.get("question");
    const session_id = searchParams.get("session_id");
    const mode = searchParams.get("mode") || "rag_llm";

    if (!question || session_id == null) {
        return NextResponse.json(
            { detail: "question and session_id are required" },
            { status: 400 }
        );
    }

    const backendUrl = `${API_URL.replace(/\/$/, "")}/v1/ask/stream`;

    const cookie = request.headers.get("cookie") || "";

    try {
        const res = await fetch(backendUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Cookie: cookie,
            },
            body: JSON.stringify({
                question,
                session_id: Number(session_id),
                mode,
            }),
            cache: "no-store",
        });

        if (!res.ok || !res.body) {
            const text = await res.text();
            try {
                const json = JSON.parse(text);
                return NextResponse.json(json, { status: res.status });
            } catch {
                return NextResponse.json(
                    { detail: text || "Erreur de l'assistant IA." },
                    { status: res.status }
                );
            }
        }

        return new Response(res.body, {
            status: res.status,
            headers: {
                "Content-Type": res.headers.get("Content-Type") || "text/plain",
            },
        });
    } catch (err) {
        console.error("Ask API proxy error:", err);
        return NextResponse.json(
            { detail: "Erreur de connexion au serveur." },
            { status: 502 }
        );
    }
}
