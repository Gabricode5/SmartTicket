const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

export function getDateGroupLabel(dateStr: string, referenceDate: Date = new Date()): string {
    const date = new Date(dateStr)
    const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diffDays = Math.round(
        (startOfDay(referenceDate).getTime() - startOfDay(date).getTime()) / 86_400_000
    )

    if (diffDays === 0) return "Aujourd'hui"
    if (diffDays === 1) return "Hier"
    if (diffDays > 1 && diffDays <= 7) return "7 derniers jours"
    if (diffDays > 7 && diffDays <= 30) return "30 derniers jours"
    return capitalize(date.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }))
}

export type DateGroup<T> = { label: string; items: T[] }

// Groups items by date bucket without re-sorting — callers must already
// pass items sorted by date (desc), which is how the API returns sessions.
export function groupByDate<T extends { date_creation?: string | null }>(
    items: T[],
    referenceDate: Date = new Date()
): DateGroup<T>[] {
    const groups: DateGroup<T>[] = []
    const indexByLabel = new Map<string, number>()

    for (const item of items) {
        const label = item.date_creation ? getDateGroupLabel(item.date_creation, referenceDate) : "Sans date"
        let idx = indexByLabel.get(label)
        if (idx === undefined) {
            idx = groups.length
            indexByLabel.set(label, idx)
            groups.push({ label, items: [] })
        }
        groups[idx].items.push(item)
    }

    return groups
}
