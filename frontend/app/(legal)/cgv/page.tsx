export const metadata = { title: "Conditions générales de vente — SmartTicket" }

export default function CgvPage() {
    return (
        <>
            <div>
                <h1 className="text-2xl font-bold text-slate-900">Conditions générales de vente</h1>
                <p className="text-xs text-slate-400 mt-1">Dernière mise à jour : [DATE]</p>
            </div>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Article 1 — Objet</h2>
                <p>
                    Les présentes conditions générales de vente (CGV) régissent la fourniture, par
                    [RAISON SOCIALE À COMPLÉTER] (ci-après « SmartTicket »), du service SmartTicket, une plateforme
                    de support client assistée par intelligence artificielle, à toute entreprise cliente
                    (ci-après « le Client ») qui y souscrit.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Article 2 — Description du service</h2>
                <p>
                    SmartTicket fournit une instance dédiée comprenant : un assistant IA répondant aux questions des
                    utilisateurs finaux du Client à partir de sa base de connaissances, un système de transfert vers
                    des agents humains, des outils de gestion d&apos;équipe support et des tableaux de bord d&apos;analyse.
                    Le détail des fonctionnalités incluses dépend du palier souscrit, précisé dans les conditions
                    particulières (devis ou bon de commande).
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Article 3 — Prix et modalités de paiement</h2>
                <p>
                    Les tarifs applicables sont ceux figurant dans le devis ou les conditions particulières acceptés
                    par le Client. Sauf mention contraire, la facturation est mensuelle ou annuelle, payable
                    d&apos;avance. [MODALITÉS DE PAIEMENT ET PÉNALITÉS DE RETARD À COMPLÉTER]
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Article 4 — Durée et résiliation</h2>
                <p>
                    Le contrat est conclu pour la durée précisée dans les conditions particulières. Chaque partie
                    peut résilier moyennant un préavis de [DURÉE À COMPLÉTER]. En cas de résiliation, le Client
                    dispose d&apos;un délai de 30 jours pour exporter ses données avant leur suppression définitive.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Article 5 — Responsabilités</h2>
                <p>
                    SmartTicket s&apos;engage à fournir le service avec diligence, sans garantir une disponibilité
                    ininterrompue. Les engagements de niveau de service (disponibilité, délai de réponse support)
                    font l&apos;objet d&apos;un document séparé (SLA) lorsque celui-ci est prévu aux conditions
                    particulières. Les réponses générées par l&apos;assistant IA s&apos;appuient sur la base de
                    connaissances fournie par le Client ; SmartTicket ne garantit pas l&apos;exactitude de ces
                    réponses et le Client reste responsable de la supervision de son service client.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Article 6 — Protection des données</h2>
                <p>
                    Le traitement des données personnelles est régi par notre{" "}
                    <a href="/politique-confidentialite" className="text-indigo-600 hover:underline">politique de confidentialité</a>{" "}
                    et, pour les clients professionnels, par un accord de sous-traitance (DPA) conforme à l&apos;article 28
                    du RGPD, fourni sur demande.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Article 7 — Propriété intellectuelle</h2>
                <p>
                    SmartTicket demeure propriétaire de la plateforme, de son code source et de sa marque. Le Client
                    conserve l&apos;entière propriété de sa base de connaissances et des données de ses utilisateurs
                    finaux.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Article 8 — Droit applicable</h2>
                <p>
                    Les présentes CGV sont soumises au droit français. Tout litige relève, à défaut de résolution
                    amiable, des tribunaux compétents du ressort de [VILLE À COMPLÉTER].
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Contact</h2>
                <p>Pour toute question relative aux présentes CGV : [EMAIL DE CONTACT À COMPLÉTER].</p>
            </section>
        </>
    )
}
