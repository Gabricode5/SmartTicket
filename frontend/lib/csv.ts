type CsvSection = {
    title: string
    headers: string[]
    rows: (string | number)[][]
}

function escapeCsvCell(value: string | number): string {
    const str = String(value)
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str
}

/** Builds a multi-section CSV (blank line between sections) and triggers a browser download. */
export function downloadCsv(filename: string, sections: CsvSection[]) {
    const lines: string[] = []
    for (const section of sections) {
        lines.push(section.title)
        lines.push(section.headers.map(escapeCsvCell).join(","))
        for (const row of section.rows) {
            lines.push(row.map(escapeCsvCell).join(","))
        }
        lines.push("")
    }
    // Leading BOM so Excel opens the UTF-8 file with accents rendered correctly.
    const BOM = String.fromCharCode(0xfeff)
    const blob = new Blob([BOM + lines.join("\r\n")], { type: "text/csv;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}
