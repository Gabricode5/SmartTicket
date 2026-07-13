const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

export type DateGroupLabels = {
    today: string
    yesterday: string
    last7Days: string
    last30Days: string
    noDate: string
}

// Défauts en français pour les appelants qui ne passent pas encore de traductions
// (ex. SavDashboard.tsx, pas encore internationalisé) — évite de devoir toucher
// tous les call sites à chaque extension du périmètre traduit.
export const DEFAULT_DATE_GROUP_LABELS: DateGroupLabels = {
    today: "Aujourd'hui",
    yesterday: "Hier",
    last7Days: "7 derniers jours",
    last30Days: "30 derniers jours",
    noDate: "Sans date",
}

export function getDateGroupLabel(
    dateStr: string,
    referenceDate: Date = new Date(),
    labels: DateGroupLabels = DEFAULT_DATE_GROUP_LABELS,
    locale: string = "fr-FR"
): string {
    const date = new Date(dateStr)
    const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diffDays = Math.round(
        (startOfDay(referenceDate).getTime() - startOfDay(date).getTime()) / 86_400_000
    )

    if (diffDays === 0) return labels.today
    if (diffDays === 1) return labels.yesterday
    if (diffDays > 1 && diffDays <= 7) return labels.last7Days
    if (diffDays > 7 && diffDays <= 30) return labels.last30Days
    return capitalize(date.toLocaleDateString(locale, { month: "long", year: "numeric" }))
}

export type DateGroup<T> = { label: string; items: T[] }

// Groups items by date bucket without re-sorting — callers must already
// pass items sorted by date (desc), which is how the API returns sessions.
export function groupByDate<T extends { date_creation?: string | null }>(
    items: T[],
    referenceDate: Date = new Date(),
    labels: DateGroupLabels = DEFAULT_DATE_GROUP_LABELS,
    locale: string = "fr-FR"
): DateGroup<T>[] {
    const groups: DateGroup<T>[] = []
    const indexByLabel = new Map<string, number>()

    for (const item of items) {
        const label = item.date_creation ? getDateGroupLabel(item.date_creation, referenceDate, labels, locale) : labels.noDate
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
