"use client"

import { AppSidebar } from "@/components/app-sidebar"

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
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

