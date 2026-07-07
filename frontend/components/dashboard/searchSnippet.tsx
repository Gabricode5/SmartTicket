import type { ReactNode } from "react"

// ts_headline (Postgres) wraps matched terms in <b>...</b> without escaping the
// rest of the text. We never trust it as HTML (no dangerouslySetInnerHTML) —
// we only split on our own known <b>/</b> markers and let React render the
// surrounding text as plain (auto-escaped) text nodes.
export function renderSnippet(snippet: string): ReactNode[] {
    const nodes: ReactNode[] = []
    const regex = /<b>(.*?)<\/b>/g
    let lastIndex = 0
    let match: RegExpExecArray | null
    let key = 0
    while ((match = regex.exec(snippet)) !== null) {
        if (match.index > lastIndex) nodes.push(snippet.slice(lastIndex, match.index))
        nodes.push(<strong key={key++}>{match[1]}</strong>)
        lastIndex = regex.lastIndex
    }
    if (lastIndex < snippet.length) nodes.push(snippet.slice(lastIndex))
    return nodes
}
