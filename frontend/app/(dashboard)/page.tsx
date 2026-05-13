"use client"

import { useEffect, useState } from "react"
import AdminDashboard from "@/components/dashboard/AdminDashboard"
import SavDashboard from "@/components/dashboard/SavDashboard"
import UserDashboard from "@/components/dashboard/UserDashboard"

export default function DashboardPage() {
    const [role, setRole] = useState<string | null>(null)

    useEffect(() => {
        setRole(localStorage.getItem("user_role") || "user")
    }, [])

    if (!role) return null
    if (role === "admin") return <AdminDashboard />
    if (role === "sav") return <SavDashboard />
    return <UserDashboard />
}
