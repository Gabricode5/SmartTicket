"use client"

import { useCurrentUser } from "@/hooks/useCurrentUser"
import AdminDashboard from "@/components/dashboard/AdminDashboard"
import SavDashboard from "@/components/dashboard/SavDashboard"
import SupervisorDashboard from "@/components/dashboard/SupervisorDashboard"
import UserDashboard from "@/components/dashboard/UserDashboard"
import OnboardingModal from "@/components/onboarding/OnboardingModal"

export default function DashboardPage() {
    const { user, isLoading } = useCurrentUser()

    if (isLoading || !user) return null

    return (
        <>
            <OnboardingModal userId={user.id} role={user.role} />
            {user.role === "admin" ? (
                <AdminDashboard currentUserId={user.id} />
            ) : user.role === "superviseur" ? (
                <SupervisorDashboard />
            ) : user.role === "sav" ? (
                <SavDashboard />
            ) : (
                <UserDashboard userId={user.id} />
            )}
        </>
    )
}
