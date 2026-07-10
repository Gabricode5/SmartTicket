import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export function proxy(request: NextRequest) {
    const authToken = request.cookies.get("auth_token")?.value
    const pathname = request.nextUrl.pathname

    // Tout fichier statique servi depuis public/ (logo, images, polices...) doit être
    // public, quel que soit son nom — jamais couvert par la liste des routes ci-dessous,
    // qui ne concerne que des pages Next.js. Repéré par extension plutôt que par nom
    // explicite : une vraie page App Router n'a jamais de point dans son dernier segment
    // (contrairement à "/logo.png"), donc ce test ne peut pas laisser passer une page par
    // erreur. Sans ça, un visiteur anonyme reçoit une redirection HTML vers /login à la
    // place du fichier demandé (leçon apprise en prod : /logo_smartticket.png renvoyait un
    // 307 au lieu de l'image, exactement le même bug de fond que /verify-email plus tôt).
    const isStaticAsset = /\.[a-zA-Z0-9]+$/.test(pathname)

    const isPublicPath =
        isStaticAsset ||
        pathname === "/" ||
        pathname === "/login" ||
        pathname === "/sign-up" ||
        pathname === "/forgot-password" ||
        pathname === "/verify-email" ||
        pathname === "/reset-password" ||
        pathname === "/setup" ||
        pathname === "/chat" ||
        pathname === "/mentions-legales" ||
        pathname === "/politique-confidentialite" ||
        pathname === "/cgv" ||
        pathname.startsWith("/_next") ||
        pathname.startsWith("/static")

    if (!isPublicPath && !authToken) {
        return NextResponse.redirect(new URL("/login", request.url))
    }

    if (authToken && pathname === "/login") {
        return NextResponse.redirect(new URL("/dashboard", request.url))
    }

    return NextResponse.next()
}

export const config = {
    matcher: [
        "/((?!api|_next/static|_next/image|favicon.ico).*)",
    ],
}
