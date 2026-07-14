"use client"

import { useLocale } from "@/lib/i18n/LocaleContext"

export default function PolitiqueConfidentialiteContent() {
    const { messages: t } = useLocale()
    const p = t.legal.privacy
    return (
        <>
            <div>
                <h1 className="text-2xl font-bold text-slate-900">{p.title}</h1>
                <p className="text-xs text-slate-400 mt-1">{t.legal.lastUpdated}</p>
            </div>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{p.controllerTitle}</h2>
                <p>
                    {p.controllerBody}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{p.dataCollectedTitle}</h2>
                <p>{p.dataCollectedIntro}</p>
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="border-b border-slate-200">
                                <th className="py-2 pr-4 font-semibold">{p.tableData}</th>
                                <th className="py-2 pr-4 font-semibold">{p.tablePurpose}</th>
                                <th className="py-2 font-semibold">{p.tableLegalBasis}</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="border-b border-slate-100">
                                <td className="py-2 pr-4">{p.rowEmailData}</td>
                                <td className="py-2 pr-4">{p.rowEmailPurpose}</td>
                                <td className="py-2">{p.rowContractExecution}</td>
                            </tr>
                            <tr className="border-b border-slate-100">
                                <td className="py-2 pr-4">{p.rowUsernameData}</td>
                                <td className="py-2 pr-4">{p.rowUsernamePurpose}</td>
                                <td className="py-2">{p.rowContractExecution}</td>
                            </tr>
                            <tr className="border-b border-slate-100">
                                <td className="py-2 pr-4">{p.rowPasswordData}</td>
                                <td className="py-2 pr-4">{p.rowPasswordPurpose}</td>
                                <td className="py-2">{p.rowContractExecution}</td>
                            </tr>
                            <tr>
                                <td className="py-2 pr-4">{p.rowMessagesData}</td>
                                <td className="py-2 pr-4">{p.rowMessagesPurpose}</td>
                                <td className="py-2">{p.rowMessagesLegalBasis}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{p.recipientsTitle}</h2>
                <p>
                    {p.recipientsIntro}
                </p>
                <ul className="list-disc list-inside space-y-1">
                    <li><strong>Mistral AI</strong> — {p.mistralDesc}</li>
                    <li><strong>Render</strong> — {p.renderDesc}</li>
                    <li><strong>Brevo</strong> — {p.brevoDesc}</li>
                </ul>
                <p>{p.noTransferOutsideEu}</p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{p.retentionTitle}</h2>
                <p>
                    {p.retentionBody}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{p.cookiesTitle}</h2>
                <p>
                    {p.cookiesBodyPrefix}<code>auth_token</code>{p.cookiesBodyMiddle}<code>httpOnly</code>, <code>SameSite=strict</code>{p.cookiesBodySuffix}
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{p.securityTitle}</h2>
                <ul className="list-disc list-inside space-y-1">
                    <li>{p.securityItem1}</li>
                    <li>{p.securityItem2Prefix} <code>httpOnly</code></li>
                    <li>{p.securityItem3}</li>
                    <li>{p.securityItem4}</li>
                </ul>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">{p.rightsTitle}</h2>
                <p>{p.rightsIntro}</p>
                <ul className="list-disc list-inside space-y-1">
                    <li><strong>{p.rightAccess}</strong> — {p.rightAccessDesc}</li>
                    <li><strong>{p.rightRectification}</strong> — {p.rightRectificationDesc}</li>
                    <li><strong>{p.rightPortability}</strong> — {p.rightPortabilityDesc}</li>
                    <li><strong>{p.rightErasure}</strong> — {p.rightErasureDesc}</li>
                    <li><strong>{p.rightObjection}</strong> — {p.rightObjectionDesc}</li>
                </ul>
                <p>
                    {p.exerciseRightsPrefix}
                    <a href="https://www.cnil.fr" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">cnil.fr</a>).
                </p>
            </section>
        </>
    )
}
