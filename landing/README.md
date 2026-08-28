# Tiqia — landing page (site statique)

Extrait autonome de `frontend/app/page.tsx` : uniquement la landing marketing,
exportée en HTML/CSS/JS statique (`next build` avec `output: "export"`), sans
dépendance au backend ni au reste de l'app (auth, chat, dashboard).

Unique CTA : "Demander une démo" (`mailto:contact@tiqia.fr`). Les boutons
"Se connecter" ont été retirés le 2026-08-28 : la connexion client mono-tenant
n'a pas de destination valide depuis la landing (cf. ROADMAP, à la 1re signature).
Les pages légales (`/mentions-legales`, `/politique-confidentialite`, `/cgv`) sont
servies localement par cette landing (identifient l'entité Tiqia elle-même, pas
une instance client — retirées de `frontend/` le 2026-08-25).

## Dev local

```bash
npm install
npm run dev
```

## Build statique

```bash
npm install
npm run build
```

Génère `out/` (HTML/CSS/JS statiques, prêts à servir).

## Déploiement sur Render

### Option A — via le dashboard (le plus simple)

1. New → Static Site
2. Connecter le repo, **Root Directory**: `landing`
3. Build Command: `npm install && npm run build`
4. Publish directory: `out`

### Option B — via Blueprint

Créer un Blueprint Render en pointant le **Blueprint path** vers
`landing/render.yaml` (le render.yaml à la racine du repo gère backend +
frontend complet séparément, celui-ci ne déploie que la landing).
