import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export function proxy(request: NextRequest) {
    const authToken = request.cookies.get("auth_token")?.value
    const pathname = request.nextUrl.pathname

    const isPublicPath =
        pathname === "/login" ||
        pathname === "/sign-up" ||
        pathname === "/forgot-password" ||
        pathname.startsWith("/_next") ||
        pathname === "/favicon.ico" ||
        pathname.startsWith("/static")

    if (!isPublicPath && !authToken) {
        return NextResponse.redirect(new URL("/login", request.url))
    }

    if (authToken && pathname === "/login") {
        return NextResponse.redirect(new URL("/", request.url))
    }

    return NextResponse.next()
}

export const config = {
    matcher: [
        "/((?!api|_next/static|_next/image|favicon.ico).*)",
    ],
}
