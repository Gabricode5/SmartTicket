"use client"

import { useLocale } from "@/lib/i18n/LocaleContext"

export default function MentionsLegalesContent() {
    const { messages: t } = useLocale()
    return (
        <>
            <div>
                <h1 className="text-2xl font-bold text-slate-900">{t.legal.mentions.title}</h1>
                <p className="text-xs text-slate-400 mt-1">{t.legal.lastUpdated}</p>
            </div>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{t.legal.mentions.publisherTitle}</h2>
                <p>
                    {t.legal.mentions.publisherIntro}
                </p>
                <ul className="list-disc list-inside space-y-1">
                    <li>{t.legal.mentions.companyName}</li>
                    <li>{t.legal.mentions.legalForm}</li>
                    <li>{t.legal.mentions.siren}</li>
                    <li>{t.legal.mentions.address}</li>
                    <li>{t.legal.mentions.director}</li>
                    <li>{t.legal.mentions.contactItem}</li>
                </ul>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{t.legal.mentions.hostingTitle}</h2>
                <p>
                    {t.legal.mentions.hostingBodyPrefix}{" "}
                    <a href="https://render.com" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">
                        render.com
                    </a>.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{t.legal.mentions.ipTitle}</h2>
                <p>
                    {t.legal.mentions.ipBody}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{t.legal.mentions.contactTitle}</h2>
                <p>
                    {t.legal.mentions.contactBodyPrefix}{" "}
                    {t.legal.mentions.contactEmailPlaceholder}.
                </p>
            </section>
        </>
    )
}
