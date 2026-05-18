# Référentiel d'accessibilité

**Projet :** SmartTicket — Gestionnaire de tickets intelligent avec assistant virtuel  
**Standard :** WCAG 2.1 niveau AA

---

## 1. Déclaration de conformité

Le projet SmartTicket vise la conformité au standard **Web Content Accessibility Guidelines (WCAG) 2.1, niveau AA**, publié par le W3C le 5 juin 2018.

Référence officielle : [https://www.w3.org/TR/WCAG21/](https://www.w3.org/TR/WCAG21/)  
Traduction française de référence : [https://www.w3.org/Translations/WCAG21-fr/](https://www.w3.org/Translations/WCAG21-fr/)

La conformité WCAG 2.1 AA impose de satisfaire **l'ensemble des critères de niveau A et AA** définis par le W3C. Les 4 principes directeurs sont : **Perceptible, Utilisable, Compréhensible, Robuste** (POUR).

Cette déclaration couvre les interfaces suivantes :
- Widget de chat (interface client)
- Espace "Mes tickets" (interface client)
- Dashboard opérateur SAV
- Interface d'administration de la base documentaire
- Page Analytics (tableaux de bord métriques)

---

## 2. Tableau de couverture — 13 critères WCAG 2.1 AA sélectionnés

| # | Critère | Niveau | Application concrète au projet SmartTicket | Méthode de vérification |
|---|---|:---:|---|---|
| 1 | **1.1.1 Contenu non textuel** | A | Chaque graphique Recharts du dashboard Analytics dispose d'un `aria-label` descriptif sur le SVG et d'un tableau de données alternatif masqué visuellement (`sr-only`) mais lisible par les lecteurs d'écran. Les icônes de statut (tickets, rôles) ont un `alt` ou `aria-label`. | Audit NVDA/VoiceOver : chaque graphique doit être annoncé avec son titre et ses valeurs clés sans interaction visuelle. |
| 2 | **1.3.1 Information et relations** | A | L'historique des messages du chat est structuré en éléments `<article>` ou `<li>` avec un `<header>` identifiant l'auteur (Client, Bot, Opérateur) lisible par les technologies d'assistance, indépendamment de la couleur de bulle. Les formulaires utilisent des `<label>` liés par `for` / `id`. | Audit avec axe-core / WAVE : aucune information transmise uniquement par mise en forme (absence d'erreur "label manquant"). |
| 3 | **1.4.1 Utilisation de la couleur** | A | Les badges de statut des tickets (`open`, `transferred`, `resolved`, `closed`) affichent un libellé textuel en plus de la couleur. Les graphiques Recharts différencient les séries par forme de point (rond, carré, triangle) ou motif de ligne (plein, tirets) en plus de la couleur. | Test en niveaux de gris (filtre navigateur) : toutes les informations restent intelligibles. |
| 4 | **1.4.3 Contraste minimum** | AA | Tout texte de corps de taille < 18 pt (ou < 14 pt gras) respecte un ratio de contraste ≥ 4,5:1 par rapport à l'arrière-plan. Cela couvre les bulles de chat, les labels de formulaire, les valeurs numériques du dashboard, et les textes de navigation, en mode clair et dark. | WebAIM Contrast Checker ou Colour Contrast Analyser sur toutes les combinaisons texte/fond des thèmes clair et sombre. |
| 5 | **1.4.4 Redimensionnement du texte** | AA | Tous les textes de l'interface sont redimensionnables jusqu'à 200 % via le zoom navigateur (Ctrl++), sans perte de contenu ni chevauchement. Le widget de chat, les tableaux de la knowledge base et le dashboard restent lisibles et opérables à 200 %. | Test manuel à 200 % de zoom dans Chrome/Firefox : aucun texte tronqué, aucun composant inaccessible. |
| 6 | **1.4.10 Redistribution** | AA | L'interface est utilisable sans défilement horizontal à une largeur de 320 px CSS (équivalent 1 280 px à 400 % de zoom). Le widget de chat, les formulaires d'ingestion et la liste des tickets s'adaptent en colonne unique à cette largeur. | Test Chrome DevTools en responsive 320 px : aucun défilement horizontal, aucun contenu masqué. |
| 7 | **1.4.11 Contraste des composants non textuels** | AA | Les bordures des champs de saisie, les contours des boutons (Envoyer, Feedback, Upload) et les contrôles de formulaire ont un ratio de contraste ≥ 3:1 par rapport à l'arrière-plan adjacent, en état normal et focus. | Colour Contrast Analyser : mesurer bordure de champ vs fond de page pour chaque thème. |
| 8 | **2.1.1 Clavier** | A | Toute fonctionnalité est accessible au clavier : envoi d'un message (Entrée), navigation entre les tickets (Tab / Shift+Tab), sélection d'un motif de transfert (flèches + Espace), upload de fichier (Tab + Entrée), navigation dans le dashboard (Tab). Aucun piège clavier. | Test de navigation complète au clavier sans souris : toutes les actions des user stories US-01 à US-08 doivent être accomplissables. |
| 9 | **2.4.3 Ordre de focus** | A | L'ordre de tabulation suit la séquence logique de lecture : en-tête → navigation principale → contenu principal (liste de tickets ou historique chat) → champ de saisie → bouton Envoyer → pied de page. Les modales (transfert, confirmation suppression) capturent le focus à leur ouverture et le restituent à l'élément déclencheur à la fermeture. | Test Tab séquentiel : l'ordre de focus ne "saute" jamais au-delà du contenu visible ni ne retourne en arrière de manière inattendue. |
| 10 | **2.4.6 En-têtes et étiquettes** | AA | Chaque page a une hiérarchie de titres `<h1>` → `<h2>` → `<h3>` cohérente. Les sections du dashboard (KPIs, Graphiques, Alertes) ont des titres `<h2>`. Le panneau d'historique d'une session a un `<h2>` identifiant le ticket et le client. Les champs de formulaire ont tous un `<label>` descriptif. | Audit Headings Map (extension navigateur) : aucun saut de niveau, aucun titre générique ("Section"). |
| 11 | **2.4.7 Visibilité du focus** | AA | Tous les éléments interactifs (boutons, liens, champs, boutons de feedback, éléments de liste cliquables) affichent un indicateur de focus visible : contour d'au moins 2 px avec un ratio de contraste ≥ 3:1 entre le contour et l'arrière-plan. Le style CSS `outline: none` est proscrit sans remplacement. | Test Tab + inspection visuelle : le focus est visible sur chaque élément interactif des 5 interfaces couvertes. |
| 12 | **3.3.1 Identification des erreurs** | A | Les erreurs de formulaire (champ vide, message trop long, URL invalide, format de fichier non supporté) sont identifiées textuellement et associées au champ en erreur via `aria-describedby`. Le message décrit précisément l'erreur : "L'URL saisie est inaccessible (erreur 404)" plutôt qu'un générique "Erreur". | Test des cas d'erreur de chaque formulaire avec NVDA : le message d'erreur est annoncé à la soumission du formulaire, lié au champ concerné. |
| 13 | **4.1.3 Messages d'état** | AA | Les changements d'état dynamiques sont annoncés aux lecteurs d'écran via des régions `aria-live` : chargement de la réponse bot (`aria-live="polite"`), confirmation de transfert vers opérateur (`aria-live="assertive"`), fin d'ingestion d'un document (`aria-live="polite"`), confirmation de feedback enregistré (`aria-live="polite"`). | Test NVDA/VoiceOver sur les 4 cas : l'annonce est prononcée sans déplacement manuel du focus. |

---

## 3. Mapping user stories → critères WCAG

Ce tableau montre quels critères WCAG couvrent chaque user story, permettant de tracer la conformité d'accessibilité à chaque fonctionnalité.

| User Story | Titre | Critères WCAG 2.1 AA appliqués |
|---|---|---|
| **US-01** | Poser une question en langage naturel | 2.1.1 Clavier · 4.1.2 Nom, rôle, valeur |
| **US-02** | Recevoir une réponse RAG | 4.1.3 Messages d'état · 1.4.3 Contraste minimum |
| **US-03** | Escalade vers un opérateur humain | 4.1.3 Messages d'état · 3.3.2 Étiquettes ou instructions |
| **US-04** | Suivre l'état d'un ticket | 1.4.1 Utilisation de la couleur · 4.1.2 Nom, rôle, valeur |
| **US-05** | Reprendre une conversation (Opérateur) | 1.3.1 Information et relations · 2.4.6 En-têtes et étiquettes |
| **US-06** | Évaluer la qualité d'une réponse bot | 4.1.2 Nom, rôle, valeur · 2.4.7 Visibilité du focus |
| **US-07** | Gérer la base documentaire (Admin) | 3.3.1 Identification des erreurs · 1.4.10 Redistribution |
| **US-08** | Consulter le tableau de bord métriques | 1.1.1 Contenu non textuel · 1.4.1 Utilisation de la couleur |

### Couverture transversale (tous parcours)

Les critères suivants s'appliquent à l'ensemble des interfaces sans être rattachés à une user story spécifique :

| Critère | Application transversale |
|---|---|
| 1.4.4 Redimensionnement du texte | Toutes les pages : zoom navigateur 200 % |
| 1.4.10 Redistribution | Toutes les pages : responsive 320 px |
| 1.4.11 Contraste composants non textuels | Tous les champs, boutons, contrôles |
| 2.1.1 Clavier | Toutes les interactions sans souris |
| 2.4.3 Ordre de focus | Navigation globale + modales |
| 2.4.7 Visibilité du focus | Tous les éléments interactifs |

---

## 4. Outils de vérification recommandés

| Outil | Usage | Critères couverts |
|---|---|---|
| **axe-core** (extension navigateur ou CI) | Audit automatisé WCAG | 1.1.1, 1.3.1, 2.1.1, 4.1.2 |
| **WAVE** (WebAIM) | Détection erreurs structures HTML | 1.3.1, 2.4.6, 3.3.1 |
| **Colour Contrast Analyser** (TPGi) | Mesure ratios de contraste | 1.4.3, 1.4.11 |
| **NVDA** (Windows) + Firefox | Test lecteur d'écran | 4.1.3, 1.1.1, 3.3.1 |
| **VoiceOver** (macOS/iOS) + Safari | Test lecteur d'écran | 4.1.3, 4.1.2 |
| **Chrome DevTools** (responsive) | Test redistribution 320 px | 1.4.10 |
| **Zoom navigateur 200 %** | Test redimensionnement | 1.4.4 |
