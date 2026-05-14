"use client"

import { useCurrentUser } from "@/hooks/useCurrentUser"
import AdminDashboard from "@/components/dashboard/AdminDashboard"
import SavDashboard from "@/components/dashboard/SavDashboard"
import UserDashboard from "@/components/dashboard/UserDashboard"

export default function DashboardPage() {
    const { user, isLoading } = useCurrentUser()

    if (isLoading || !user) return null
    if (user.role === "admin") return <AdminDashboard currentUserId={user.id} />
    if (user.role === "sav") return <SavDashboard />
    return <UserDashboard userId={user.id} />
}
