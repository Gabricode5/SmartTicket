export const metadata = { title: "Politique de confidentialité — SmartTicket" }

export default function PolitiqueConfidentialitePage() {
    return (
        <>
            <div>
                <h1 className="text-2xl font-bold text-slate-900">Politique de confidentialité</h1>
                <p className="text-xs text-slate-400 mt-1">Dernière mise à jour : [DATE]</p>
            </div>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Responsable de traitement</h2>
                <p>
                    [RAISON SOCIALE À COMPLÉTER], [ADRESSE À COMPLÉTER], est responsable du traitement des données
                    personnelles décrit ci-dessous. Contact : [EMAIL DE CONTACT / DPO À COMPLÉTER].
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Données collectées</h2>
                <p>Lors de la création et de l&apos;utilisation d&apos;un compte, nous collectons :</p>
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="border-b border-slate-200">
                                <th className="py-2 pr-4 font-semibold">Donnée</th>
                                <th className="py-2 pr-4 font-semibold">Finalité</th>
                                <th className="py-2 font-semibold">Base légale</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="border-b border-slate-100">
                                <td className="py-2 pr-4">Email</td>
                                <td className="py-2 pr-4">Authentification, identifiant unique, communications liées au compte</td>
                                <td className="py-2">Exécution du contrat</td>
                            </tr>
                            <tr className="border-b border-slate-100">
                                <td className="py-2 pr-4">Nom d&apos;utilisateur, prénom, nom</td>
                                <td className="py-2 pr-4">Identification, personnalisation de l&apos;interface</td>
                                <td className="py-2">Exécution du contrat</td>
                            </tr>
                            <tr className="border-b border-slate-100">
                                <td className="py-2 pr-4">Mot de passe</td>
                                <td className="py-2 pr-4">Sécurisation du compte (haché, jamais stocké en clair)</td>
                                <td className="py-2">Exécution du contrat</td>
                            </tr>
                            <tr>
                                <td className="py-2 pr-4">Messages échangés (conversations)</td>
                                <td className="py-2 pr-4">Fourniture du service de support, historique client</td>
                                <td className="py-2">Exécution du contrat / intérêt légitime</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Destinataires des données</h2>
                <p>
                    Les données ne sont jamais vendues ni transmises à des fins commerciales. Elles peuvent être
                    transmises aux sous-traitants techniques suivants, strictement nécessaires au fonctionnement
                    du Service :
                </p>
                <ul className="list-disc list-inside space-y-1">
                    <li><strong>Mistral AI</strong> — génération des réponses de l&apos;assistant IA à partir du contenu de la question posée</li>
                    <li><strong>Render</strong> — hébergement de l&apos;application et de la base de données (Union européenne, région Frankfurt)</li>
                    <li><strong>Brevo</strong> — envoi des emails transactionnels (vérification de compte, réinitialisation de mot de passe, notifications)</li>
                </ul>
                <p>Aucune donnée n&apos;est transférée hors de l&apos;Union européenne.</p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Durée de conservation</h2>
                <p>
                    Les données sont conservées tant que le compte existe. En cas de suppression de compte, les
                    données sont marquées pour suppression et effacées définitivement au plus tard 30 jours après
                    la demande.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Cookies</h2>
                <p>
                    Le Service utilise un unique cookie technique (<code>auth_token</code>), strictement nécessaire
                    au maintien de la session de connexion (<code>httpOnly</code>, <code>SameSite=strict</code>).
                    Aucun cookie de mesure d&apos;audience ou de publicité n&apos;est utilisé.
                </p>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Sécurité</h2>
                <ul className="list-disc list-inside space-y-1">
                    <li>Mots de passe hachés (bcrypt), jamais stockés en clair</li>
                    <li>Connexion sécurisée par jeton signé (JWT) et cookie <code>httpOnly</code></li>
                    <li>Contrôle d&apos;accès par rôle sur chaque endpoint de l&apos;application</li>
                    <li>Suppression en cascade de toutes les données liées à un compte lors de sa suppression</li>
                </ul>
            </section>

            <section className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-900">Vos droits</h2>
                <p>Conformément au RGPD, vous disposez des droits suivants sur vos données personnelles :</p>
                <ul className="list-disc list-inside space-y-1">
                    <li><strong>Droit d&apos;accès</strong> — consulter les données de votre compte depuis Paramètres</li>
                    <li><strong>Droit de rectification</strong> — modifier votre nom d&apos;utilisateur, email, prénom et nom depuis Paramètres</li>
                    <li><strong>Droit à la portabilité</strong> — télécharger l&apos;intégralité de vos données au format PDF depuis Paramètres</li>
                    <li><strong>Droit à l&apos;effacement</strong> — demander la suppression de votre compte et de toutes les données associées</li>
                    <li><strong>Droit d&apos;opposition</strong> — vous opposer à un traitement, sous réserve de motifs légitimes</li>
                </ul>
                <p>
                    Pour exercer ces droits, utilisez les fonctionnalités disponibles dans Paramètres ou contactez-nous
                    à [EMAIL DE CONTACT / DPO À COMPLÉTER]. Vous pouvez également introduire une réclamation auprès de
                    la CNIL (<a href="https://www.cnil.fr" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">cnil.fr</a>).
                </p>
            </section>
        </>
    )
}
