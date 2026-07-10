export const metadata = { title: "Mentions légales — SmartTicket" }

export default function MentionsLegalesPage() {
    return (
        <>
            <div>
                <h1 className="text-2xl font-bold text-slate-900">Mentions légales</h1>
                <p className="text-xs text-slate-400 mt-1">Dernière mise à jour : [DATE]</p>
            </div>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Éditeur du site</h2>
                <p>
                    Le site SmartTicket (ci-après « le Service ») est édité par :
                </p>
                <ul className="list-disc list-inside space-y-1">
                    <li>Raison sociale : [RAISON SOCIALE À COMPLÉTER]</li>
                    <li>Forme juridique : [FORME JURIDIQUE À COMPLÉTER — ex. auto-entreprise, SASU]</li>
                    <li>SIREN : [SIREN À COMPLÉTER]</li>
                    <li>Adresse du siège social : [ADRESSE À COMPLÉTER]</li>
                    <li>Directeur de la publication : [NOM À COMPLÉTER]</li>
                    <li>Contact : [EMAIL DE CONTACT À COMPLÉTER]</li>
                </ul>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Hébergement</h2>
                <p>
                    Le Service est hébergé par Render Services, Inc., dans la région Frankfurt (Union européenne).
                    Coordonnées complètes de l&apos;hébergeur disponibles sur{" "}
                    <a href="https://render.com" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">
                        render.com
                    </a>.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Propriété intellectuelle</h2>
                <p>
                    L&apos;ensemble des éléments du Service (structure, textes, logos, code source) est protégé au titre
                    du droit d&apos;auteur et du droit des marques. Toute reproduction, représentation ou exploitation,
                    totale ou partielle, sans autorisation préalable, est interdite.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Contact</h2>
                <p>
                    Pour toute question relative au Service, vous pouvez nous écrire à{" "}
                    [EMAIL DE CONTACT À COMPLÉTER].
                </p>
            </section>
        </>
    )
}
