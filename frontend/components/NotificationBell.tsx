"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Bell } from "lucide-react"

type Notification = {
    id: number
    type: string
    message: string
    id_session: number | null
    read: boolean
    date_creation: string
}

const POLL_INTERVAL_MS = 20000

export function NotificationBell() {
    const router = useRouter()
    const [open, setOpen] = useState(false)
    const [unreadCount, setUnreadCount] = useState(0)
    const [notifications, setNotifications] = useState<Notification[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)

    const fetchUnreadCount = useCallback(async () => {
        try {
            const response = await fetch("/api/notifications/unread-count")
            if (!response.ok) return
            const data = await response.json()
            setUnreadCount(data.count ?? 0)
        } catch {
            // Silencieux : un badge qui rate un tick n'est pas critique.
        }
    }, [])

    useEffect(() => {
        fetchUnreadCount()
        const interval = setInterval(fetchUnreadCount, POLL_INTERVAL_MS)
        return () => clearInterval(interval)
    }, [fetchUnreadCount])

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener("mousedown", handleClickOutside)
        return () => document.removeEventListener("mousedown", handleClickOutside)
    }, [])

    async function handleToggle() {
        const next = !open
        setOpen(next)
        if (next) {
            setIsLoading(true)
            try {
                const response = await fetch("/api/notifications")
                if (response.ok) {
                    setNotifications(await response.json())
                }
            } finally {
                setIsLoading(false)
            }
        }
    }

    async function handleMarkAllRead() {
        try {
            await fetch("/api/notifications/read-all", { method: "POST" })
            setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
            setUnreadCount(0)
        } catch {
            // ignore
        }
    }

    async function handleNotificationClick(notification: Notification) {
        if (!notification.read) {
            try {
                await fetch(`/api/notifications/${notification.id}/read`, { method: "PATCH" })
                setNotifications((prev) => prev.map((n) => (n.id === notification.id ? { ...n, read: true } : n)))
                setUnreadCount((prev) => Math.max(0, prev - 1))
            } catch {
                // ignore
            }
        }
        setOpen(false)
        if (notification.id_session) {
            router.push(`/ai-assistant/${notification.id_session}`)
        }
    }

    return (
        <div className="relative" ref={containerRef}>
            <button
                type="button"
                onClick={handleToggle}
                className="relative p-2 rounded-md text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
                title="Notifications"
                aria-label="Notifications"
            >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                    <span className="absolute top-0.5 right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                        {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                )}
            </button>

            {open && (
                <div className="absolute left-0 top-full mt-2 w-80 max-h-96 overflow-y-auto rounded-xl border border-sidebar-border bg-popover text-popover-foreground shadow-xl z-50">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-sidebar-border">
                        <span className="text-sm font-semibold">Notifications</span>
                        {notifications.some((n) => !n.read) && (
                            <button
                                type="button"
                                onClick={handleMarkAllRead}
                                className="text-xs text-primary hover:underline"
                            >
                                Tout marquer lu
                            </button>
                        )}
                    </div>

                    {isLoading ? (
                        <div className="px-4 py-6 text-sm text-muted-foreground text-center">Chargement…</div>
                    ) : notifications.length === 0 ? (
                        <div className="px-4 py-6 text-sm text-muted-foreground text-center">Aucune notification.</div>
                    ) : (
                        <ul>
                            {notifications.map((notification) => (
                                <li key={notification.id}>
                                    <button
                                        type="button"
                                        onClick={() => handleNotificationClick(notification)}
                                        className={`w-full text-left px-4 py-3 text-sm border-b border-sidebar-border last:border-b-0 hover:bg-sidebar-accent/60 transition-colors flex items-start gap-2 ${
                                            !notification.read ? "bg-primary/5" : ""
                                        }`}
                                    >
                                        {!notification.read && (
                                            <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary flex-shrink-0" />
                                        )}
                                        <span className={!notification.read ? "font-medium" : "text-muted-foreground"}>
                                            {notification.message}
                                        </span>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    )
}
