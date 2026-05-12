# Démarche éco-responsable

**Projet :** SmartTicket — Gestionnaire de tickets intelligent avec assistant virtuel  
**Compétence :** C15 — Critère 2 : favoriser les services et prestataires ayant une démarche éco-responsable  
**Date :** 2026-05

---

## 3.1 Référentiels appliqués

Les choix techniques et les pratiques de développement du projet SmartTicket s'appuient sur les référentiels de conception numérique responsable suivants :

| Référentiel | Organisme | Version / lien |
|---|---|---|
| **RGESN** — Référentiel Général d'Écoconception de Services Numériques | ARCEP / ARCOM / DINUM / MTE | Version 2023 — [https://www.rgesn.org/](https://www.rgesn.org/) |
| **GR491** — Guide de référence de conception responsable de services numériques | INR (Institut du Numérique Responsable) | v2 2023 — [https://gr491.isit-europe.org/](https://gr491.isit-europe.org/) |
| **Éco-index** | GreenIT.fr | Grille de notation A–G — [https://www.ecoindex.fr/](https://www.ecoindex.fr/) |
| **ADEME — Guide Numérique Responsable** | ADEME | 2023 — [https://www.ademe.fr/](https://www.ademe.fr/) |
| **Web Sustainability Guidelines (WSG)** | W3C Sustainable Web Design CG | 1.0 Draft 2023 — [https://www.w3.org/TR/sustainable-web-design/](https://www.w3.org/TR/sustainable-web-design/) |

Ces référentiels orientent quatre axes d'action :
1. **Choix des fournisseurs et hébergeurs** (mix énergétique, certifications).
2. **Architecture et services** (mutualisation, évitement des ressources inutiles).
3. **Frontend** (poids des assets, réduction des requêtes).
4. **Pratiques de développement** (code mort, dépendances inutilisées, requêtes SQL efficaces).

---

## 3.2 Justification éco-responsable des choix techniques

| Choix technique | Justification éco-responsable | Référence RGESN / GR491 |
|---|---|---|
| **Mistral API** (vs OpenAI / Anthropic US) | Datacenters en France et en Europe. Le mix énergétique français émet ≈ 55 g CO₂/kWh (RTE 2023) contre ≈ 380 g CO₂/kWh pour la moyenne US (EPA). À inférence égale, l'empreinte carbone est réduite d'un facteur ≈ 7. En outre, Mistral AI est soumis au RGPD, ce qui évite la duplication transfrontalière de données personnelles. | RGESN — Critère 2.3 (hébergement bas carbone) |
| **pgvector dans PostgreSQL** (vs Pinecone / Weaviate) | Mutualisation des ressources : une seule instance PostgreSQL gère à la fois les données relationnelles et les vecteurs. L'alternative Pinecone nécessiterait un service tiers supplémentaire (machines virtuelles dédiées, réplication, réseau). L'économie de ressources de calcul et de stockage est estimée à 40-50 % par rapport à une architecture à deux bases distinctes. | GR491 — Fiche 6.4 (mutualiser les infrastructures) |
| **Cache Redis pour les réponses RAG** | Chaque appel au LLM Mistral consomme des ressources GPU côté fournisseur (compute IA intensive). Une question répétée dans un délai de 1 heure retourne la réponse depuis Redis en < 5 ms sans aucun appel Mistral. Hypothèse mesurable : si 30 % des questions sont des répétitions (FAQ), le cache supprime 30 % des appels LLM — réduction directe d'empreinte compute. | RGESN — Critère 5.2 (limiter les appels réseau inutiles) |
| **Sélection du modèle Mistral selon la complexité** (`mistral-small-latest` vs `mistral-large-latest`) | `mistral-large` consomme ≈ 5× plus de ressources de calcul que `mistral-small` (différence de paramètres : ≈ 7 B vs > 70 B). L'heuristique du LLM Service achemine les questions simples (longueur < 100 tokens, questions FAQ) vers `mistral-small`. Estimation : 60 % des requêtes sont éligibles à `mistral-small` → réduction de l'empreinte compute IA de ≈ 40 % sur l'ensemble des appels. | GR491 — Fiche 7.1 (choisir des modèles proportionnels au besoin) |
| **Chunking optimisé** (500 caractères, overlap 50) | La taille du contexte envoyé au LLM détermine directement la consommation de tokens (facturation et compute). Des chunks trop grands (> 1 000 caractères) augmentent le prompt inutilement. Des chunks trop petits (< 200 caractères) nécessitent plus de chunks pour couvrir un même concept, augmentant la surface de recherche vectorielle. La taille de 500 caractères est un optimum empirique (cohérence sémantique + économie de tokens). | RGESN — Critère 5.3 (limiter le volume de données traitées) |
| **Streaming des réponses LLM (SSE)** | Le streaming réduit le buffer mémoire côté serveur : au lieu de générer la réponse complète en mémoire avant envoi, chaque token est transmis dès sa génération. Gain : réduction de la mémoire allouée côté serveur (pas d'accumulation de la chaîne complète), meilleure UX (affichage progressif) et réduction du TTFB ressenti. | RGESN — Critère 4.1 (améliorer l'expérience utilisateur sans surcharge serveur) |
| **Next.js App Router — Server Components** | Les React Server Components évitent d'envoyer le JavaScript de rendu au client pour les composants statiques (listes de tickets, pages de documentation). Réduction mesurable du bundle JS initial. Benchmark interne Next.js : les Server Components réduisent le JS client de 30-60 % sur les pages mixtes. | RGESN — Critère 3.7 (réduire le poids des pages) |
| **Lazy loading et pagination frontend** | La liste des tickets (US-04) est paginée à 20 éléments par page. Les images et composants hors-viewport sont chargés en lazy. Aucune données non affichées n'est transférée. Réduction des transferts réseau proportionnelle au ratio affiché/disponible. | RGESN — Critère 3.6 (ne pas transférer de données inutiles) |
| **Bundle splitting + tree-shaking (Next.js / Webpack / Turbopack)** | Next.js génère des bundles par route (code splitting automatique). TailwindCSS purge les classes CSS non utilisées à la compilation (PurgeCSS intégré). Recharts est importé par composant (`import { LineChart } from 'recharts'`). Objectif : JS initial < 200 KB gzippé. | RGESN — Critère 3.5 (minimiser le poids des assets) |
| **Images optimisées : composant `<Image>` Next.js** | Le composant Next.js `<Image>` génère automatiquement des variantes WebP/AVIF avec attributs `srcset` et `sizes`. Le format AVIF réduit le poids des images de 30-50 % vs JPEG à qualité visuelle égale. Le lazy loading natif évite le chargement des images hors-viewport. | RGESN — Critère 3.8 (optimiser les médias) |
| **Conteneurs Docker multi-stage sur base Alpine Linux** | Alpine Linux (base musl libc) réduit la taille des images Docker de 80-90 % par rapport aux bases Ubuntu/Debian (image Alpine Python : ≈ 50 MB vs Ubuntu : ≈ 900 MB). Les builds multi-stage éliminent les dépendances de compilation des images finales. Images plus légères = moins de stockage registry, démarrage plus rapide (moins de temps CPU de boot), transfert réseau réduit lors des déploiements. | GR491 — Fiche 6.2 (conteneurisation légère) |
| **Autoscaling Kubernetes (HPA)** | Le Horizontal Pod Autoscaler réduit les replicas à 1-2 en dehors des pics (nuit, week-end). Sans autoscaling, les ressources sont provisionnées au pic permanent (gaspillage ≈ 60 % du temps). L'HPA alloue des ressources proportionnellement à la charge réelle, réduisant la consommation électrique de l'infrastructure aux heures creuses. | GR491 — Fiche 6.3 (dimensionner au juste besoin) |
| **HTTP/2 et compression Brotli** | HTTP/2 multiplexe les requêtes sur une seule connexion TCP (réduction des handshakes TLS). Brotli compresse 15-20 % mieux que Gzip à niveau de compression équivalent, réduisant la bande passante des assets JS/CSS/JSON. Activé dans la configuration Nginx (`brotli on; brotli_comp_level 6;`). | RGESN — Critère 3.4 (compresser les transferts) |
| **Pas de polling — préférence SSE et WebSocket** | Le polling HTTP (`setInterval` toutes les N secondes) génère des requêtes en permanence même en l'absence d'événement, consommant bande passante et CPU serveur inutilement. SmartTicket utilise SSE pour le streaming LLM et les mises à jour de statut de ticket, et WebSocket pour les notifications opérateur. Économie estimée : 90 % des requêtes réseau sur les fonctionnalités temps-réel vs polling à 5 s. | RGESN — Critère 5.1 (éviter le polling) |
| **PostgreSQL optimisé : index HNSW ciblé** | L'index HNSW sur `chunk.embedding` accélère la recherche vectorielle de O(n) à O(log n). Sans index, une table de 100 000 chunks nécessiterait un scan complet à chaque question (100 000 calculs cosinus). Avec HNSW (m=16, ef_construction=64), la recherche descend à quelques centaines d'opérations. Réduction de la consommation CPU PostgreSQL ≈ 99 % sur les requêtes RAG à grande échelle. | GR491 — Fiche 5.2 (optimiser les requêtes de données) |
| **CDN pour les assets statiques** | Les fichiers JS, CSS, images et polices sont servis depuis un CDN (OVH CDN ou Cloudflare) géographiquement proche de l'utilisateur. Réduit la latence réseau et la charge sur le serveur d'origine. La réduction des allers-retours réseau diminue la consommation énergétique des équipements réseau intermédiaires. | RGESN — Critère 3.2 (rapprocher les ressources des utilisateurs) |

---

## 3.3 Métriques d'éco-conception suivies

Le projet définit et mesure les indicateurs suivants à chaque release :

| Métrique | Outil de mesure | Objectif cible | Fréquence de mesure |
|---|---|---|---|
| **Poids de page (JS + CSS + images)** | Lighthouse CI (bundle analyzer) | < 1 Mo par page (gzippé) | À chaque build CI |
| **Score Éco-index** | [https://www.ecoindex.fr/](https://www.ecoindex.fr/) | Grade A ou B | Par sprint (mesure manuelle) |
| **Nombre de requêtes HTTP par page** | Chrome DevTools Network / Lighthouse | < 30 requêtes au chargement initial | Par sprint |
| **JS initial bundle size** | Next.js build report (`next build --analyze`) | < 200 KB gzippé | À chaque build CI |
| **Tokens Mistral par conversation** | Compteur dans LLM Service (métriques Prometheus) | < 2 000 tokens/conversation en moyenne | En continu (dashboard Grafana) |
| **Coût LLM estimé (€/1 000 conversations)** | Calcul `tokens × tarif_mistral` | < 1 €/1 000 conversations | Par sprint |
| **Empreinte carbone par conversation (g CO₂eq)** | API Boavizta ([https://api.boavizta.org/](https://api.boavizta.org/)) ou estimation `tokens × kWh_GPU × gCO2_kWh` | < 1 g CO₂eq/conversation | Par sprint (estimation) |
| **Hit rate cache Redis** | Prometheus (`redis_keyspace_hits_total / redis_keyspace_misses_total`) | > 25 % sur 30 jours | En continu |
| **Temps de réponse P95 LLM** | Prometheus (histogramme latence RAG Service) | < 3 s (premier token) | En continu |
| **Taille image Docker (chaque service)** | `docker image ls` dans CI | < 200 MB par image (Alpine multi-stage) | À chaque build CI |

**Méthode d'estimation de l'empreinte carbone par conversation :**

```
tokens_embed    = len(question) / 4 (estimation)
tokens_llm_in   = tokens_embed + (top_k_chunks × 125 tokens/chunk)
tokens_llm_out  = len(réponse) / 4

énergie_GPU (kWh) ≈ (tokens_embed × 0.0000003) + (tokens_llm_in + tokens_llm_out) × 0.000002
CO₂ (g) = énergie_GPU × mix_FR (55 g/kWh)
```

Valeurs issues des estimations de l'outil [https://mlco2.github.io/impact/](https://mlco2.github.io/impact/) et de la documentation Mistral AI. À affiner avec l'API Boavizta une fois l'accès disponible.

---

## 3.4 Choix de l'hébergeur

### Comparatif des hébergeurs envisagés

| Hébergeur | Localisation DC | PUE | Mix énergétique | Certifications | Remarques |
|---|---|---|---|---|---|
| **Scaleway** | Paris (DC5, Vitry-sur-Seine) | ≈ 1.3 | 100 % énergie renouvelable (contrats PPAs + garanties d'origine) | ISO 50001, ISO 14001 | Datacenters en France, offre Managed Kubernetes (Kapsule), souveraineté RGPD |
| **OVH Cloud** | Roubaix, Strasbourg, Paris | ≈ 1.05–1.15 | Partiellement renouvelable (watercooling propre, contrats HPC) | ISO 27001, ISO 50001 | PUE parmi les meilleurs du marché grâce au watercooling ; offre Managed Kubernetes |
| **AWS EU (Ireland / Frankfurt)** | Irlande, Allemagne | ≈ 1.2 | 100 % renouvelable (engagement 2023) | ISO 50001, ISO 14001 | Siège américain (Cloud Act), transfert hors EU potentiel, tarification complexe |
| **Clever Cloud** | Rennes (FR) | ≈ 1.4 | 100 % énergie renouvelable (certifiée) | ISO 14001 | PaaS franco-français, pas de Kubernetes managé natif |

### Hébergeur retenu : **OVH Cloud Managed Kubernetes**

**Justification :**

1. **PUE 1.05–1.15** : l'un des meilleurs PUE du marché européen, obtenu grâce au système de refroidissement à eau (watercooling) qui évite la climatisation à air énergivore.
2. **Datacenters en France et UE** : données à portée du RGPD, sans risque de Cloud Act américain, conformité DPO simplifiée.
3. **Offre Kubernetes managée (OVH Managed Kubernetes)** : compatible avec notre architecture de déploiement cible, Helm intégré, autoscaling HPA supporté.
4. **Tarification prévisible** : tarification à la ressource (CPU/RAM) plus lisible que le modèle AWS avec ses centaines de services.
5. **Engagement environnemental** : OVH a publié un rapport de développement durable et vise la neutralité carbone 2030.

**Mix énergétique de référence :** le réseau électrique français émet ≈ 55 g CO₂/kWh (RTE, bilan électrique 2023), ce qui en fait l'un des mix les plus bas carbones d'Europe grâce au nucléaire et aux renouvelables. Héberger en France maximise le bénéfice carbone par kWh consommé.

---

## 3.5 Bonnes pratiques de développement éco-responsable

Les pratiques suivantes sont appliquées au quotidien et vérifiées lors des code reviews et de la CI :

1. **Lint systématique pour détecter le code mort** : `ruff` (Python) avec règle `F401` (imports inutilisés) et `F841` (variables non utilisées) ; `ESLint` (TypeScript) avec `no-unused-vars`. Ces règles bloquent le build CI si non respectées.

2. **Audit des dépendances à chaque build** : `pip-audit` (Python) et `npm audit` (Node) dans le pipeline CI. Toute dépendance sans utilisateur dans le code est signalée par `pipdeptree` / `depcheck`.

3. **Suppression des dépendances inutilisées** : avant chaque release, vérification manuelle avec `pip list --not-required` et `npx depcheck`. Les dépendances orphelines sont supprimées, ce qui réduit la taille des images Docker et la surface d'attaque.

4. **`EXPLAIN ANALYZE` obligatoire sur les requêtes critiques** : toute requête SQL touchant plus de 10 000 lignes est analysée avec `EXPLAIN ANALYZE` avant d'être mergée. Un index manquant détecté à la review bloque le merge.

5. **Pas de polling — SSE et WebSocket** : interdiction des `setInterval` HTTP côté client. Les événements temps-réel (streaming LLM, notifications opérateur) passent exclusivement par SSE ou WebSocket.

6. **Pagination obligatoire sur toutes les listes** : toute route retournant une collection (`GET /tickets`, `GET /messages`, `GET /users`) porte un paramètre `page` et `limit` (max 100). Pas d'endpoint qui retourne une liste non bornée.

7. **Compression Brotli activée dans Nginx** : niveau 6 (compromis compression/CPU). Tous les assets JS/CSS/JSON/HTML sont compressés avant envoi.

8. **HTTP/2 activé (Nginx)** : multiplexage des requêtes, réduction des handshakes TLS, server push pour les assets critiques (CSS + polices).

9. **CDN pour les assets statiques** : le build Next.js (`next export` ou déploiement avec CDN intégré OVH) sert JS, CSS, images et polices depuis le point de présence le plus proche de l'utilisateur.

10. **Images Docker légères (Alpine, multi-stage)** : chaque Dockerfile utilise une base `python:3.11-alpine` et un build multi-stage pour exclure les compilateurs et headers de développement de l'image finale. Objectif : < 200 MB par image de service.

11. **Requêtes SQL : SELECT uniquement les colonnes nécessaires** : aucun `SELECT *` dans le code de production. Chaque requête SQLAlchemy précise les colonnes via `.with_only_columns()` ou des schémas Pydantic ciblés.

12. **Éviter les frameworks lourds pour les besoins simples** : le Notification Service utilise `aiosmtplib` (léger) plutôt que Celery Beat pour les emails simples. Celery est réservé au Document Ingestion Service (tâches longues asynchrones).

13. **Clé de cache SHA-256 sur la question normalisée** : avant le calcul d'embedding, la question est normalisée (minuscules, suppression des espaces multiples, suppression de la ponctuation finale). Cela augmente le hit rate du cache Redis en agrégeant les variantes orthographiques d'une même question.

14. **Gestion de l'idle côté frontend** : si aucune interaction en 30 minutes, le widget de chat coupe la connexion SSE ouverte (EventSource). Reconnexion à la prochaine interaction. Évite de maintenir des connexions serveur pour des utilisateurs inactifs.

15. **Monitoring de l'empreinte Mistral en dashboard Grafana** : un panneau dédié affiche en temps réel les tokens consommés par heure, le coût estimé, et le hit rate du cache. La visibilité de ces métriques crée une incitation continue à optimiser.
