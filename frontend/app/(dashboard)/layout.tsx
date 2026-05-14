"use client"

import { usePathname } from "next/navigation"
import { AppSidebar } from "@/components/app-sidebar"

const PUBLIC_PATHS = ["/", "/login", "/sign-up", "/forgot-password"]

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const pathname = usePathname()

    if (PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith(p + "/"))) {
        return <>{children}</>
    }

    return (
        <div className="flex h-screen bg-background">
            <AppSidebar />

            {/* Main Content */}
            <main className="flex-1 flex flex-col overflow-hidden bg-muted/10">
                <div className="flex-1 overflow-y-auto">
                    {children}
                </div>
            </main>
        </div>
    )
}

