# C14 — Livrables de validation de compétence

**Compétence :** C14 — Analyser le besoin d'application d'un commanditaire intégrant un service d'intelligence artificielle, en rédigeant les spécifications fonctionnelles et en le modélisant, dans le respect des standards d'utilisabilité et d'accessibilité.

**Projet :** SmartTicket — Gestionnaire de tickets intelligent avec assistant virtuel (RAG + Mistral + pgvector)

---

## Livrables

| Fichier | Titre | Critères C14 validés |
|---|---|---|
| [01_specifications_fonctionnelles.md](01_specifications_fonctionnelles.md) | Spécifications fonctionnelles — User Stories | C14-3 · C14-4 · C14-5 |
| [02_modelisation_donnees.md](02_modelisation_donnees.md) | Modélisation des données — Merise (MCD/MLD/MPD) | C14-1 |
| [03_parcours_utilisateurs.md](03_parcours_utilisateurs.md) | Modélisation des parcours utilisateurs | C14-2 |
| [04_accessibilite.md](04_accessibilite.md) | Référentiel d'accessibilité WCAG 2.1 AA | C14-4 · C14-5 |

---

## Comment chaque livrable valide les critères C14

**[01 — Spécifications fonctionnelles](01_specifications_fonctionnelles.md)** valide les critères C14-3, C14-4 et C14-5 : les 8 user stories couvrent chacune le contexte d'usage, trois scénarios (nominal / alternatif / échec) et des critères d'acceptation testables et chiffrés, parmi lesquels figurent systématiquement deux critères d'acceptation explicitement étiquetés `[Accessibilité WCAG 2.1 AA — critère X.Y.Z]` avec la référence exacte au standard WCAG 2.1, satisfaisant ainsi les exigences de C14-4 (accessibilité intégrée aux critères d'acceptation) et C14-5 (appui sur un standard d'accessibilité reconnu).

**[02 — Modélisation des données](02_modelisation_donnees.md)** valide le critère C14-1 en présentant les trois niveaux du formalisme Merise : le Modèle Conceptuel de Données (MCD) avec entités, associations et cardinalités (0,1 / 1,n / 0,n) exprimées sous forme de diagramme Mermaid `erDiagram`, le Modèle Logique de Données (MLD) sous forme relationnelle textuelle avec clés primaires et étrangères, et le Modèle Physique de Données (MPD) sous forme de script SQL DDL PostgreSQL exécutable intégrant pgvector et l'index HNSW.

**[03 — Parcours utilisateurs](03_parcours_utilisateurs.md)** valide le critère C14-2 en modélisant les parcours selon plusieurs formalismes complémentaires : un diagramme de cas d'usage UML (approximé en Mermaid) listant tous les use cases des 3 acteurs, trois diagrammes de séquence détaillant les flux critiques (réponse RAG complète, escalade vers opérateur, ingestion documentaire), et trois flowcharts fonctionnels décrivant le parcours complet de chaque profil utilisateur (Client, Opérateur SAV, Administrateur).

**[04 — Référentiel d'accessibilité](04_accessibilite.md)** renforce les critères C14-4 et C14-5 en posant une déclaration explicite de conformité WCAG 2.1 AA avec lien vers la norme officielle, en détaillant 13 critères WCAG sélectionnés pour leur pertinence au projet (widget de chat, dashboard métriques, formulaires d'ingestion) avec application concrète et méthode de vérification pour chacun, et en fournissant un tableau de mapping user story → critères WCAG qui démontre la traçabilité complète entre les fonctionnalités et les exigences d'accessibilité.
