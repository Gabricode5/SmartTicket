export default function AuthLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return <div className="force-light bg-background min-h-screen">{children}</div>
}
