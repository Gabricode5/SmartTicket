"use client"

import { useLocale } from "@/lib/i18n/LocaleContext"

export default function CgvContent() {
    const { messages: t } = useLocale()
    const c = t.legal.cgv
    return (
        <>
            <div>
                <h1 className="text-2xl font-bold text-slate-900">{c.title}</h1>
                <p className="text-xs text-slate-400 mt-1">{t.legal.lastUpdated}</p>
            </div>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.article1Title}</h2>
                <p>
                    {c.article1BodyPrefix} [RAISON SOCIALE À COMPLÉTER] {c.article1BodySuffix}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.article2Title}</h2>
                <p>
                    {c.article2Body}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.article3Title}</h2>
                <p>
                    {c.article3Body}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.article4Title}</h2>
                <p>
                    {c.article4Body}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.article5Title}</h2>
                <p>
                    {c.article5Body}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.article6Title}</h2>
                <p>
                    {c.article6BodyPrefix}{" "}
                    <a href="/politique-confidentialite" className="text-indigo-600 hover:underline">{c.article6BodyLink}</a>{" "}
                    {c.article6BodySuffix}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.article7Title}</h2>
                <p>
                    {c.article7Body}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.article8Title}</h2>
                <p>
                    {c.article8Body}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{c.contactTitle}</h2>
                <p>{c.contactBody}</p>
            </section>
        </>
    )
}
