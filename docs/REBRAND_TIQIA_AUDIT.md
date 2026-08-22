# Rapport d'exploration — Rebranding SmartTicket → Tiqia

Étape 0 du rebranding : recensement seul, aucun fichier produit modifié. Ce document sert
de base de validation avant l'Étape 1 (renames effectifs).

273 occurrences de "smartticket" (insensible casse) trouvées dans le repo, hors `.git`,
`node_modules`, `.next`, `.venv`, lockfiles.

---

## (a) MARQUE VISIBLE → à remplacer par Tiqia

### Valeurs par défaut du white-label (CRITIQUE — voir section build args plus bas)
- `frontend/lib/brand.ts:5` — `export const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME || "SmartTicket";`
- `landing/lib/brand.ts:3` — même pattern

Ces deux lignes pilotent `<title>` (via `metadata.title = BRAND_NAME` dans les deux
`layout.tsx`), et tous les endroits qui affichent `alt={BRAND_NAME}` sur le logo (12
occurrences dans les pages auth/landing/legal — toutes du type
`<Image src="/logo_smartticket.png" alt={BRAND_NAME} .../>`).

### Textes UI en dur — `frontend/lib/i18n/translations.ts` (FR + EN, ~35 occurrences)
Landing pitch, sous-titres login/sign-up/setup, messages d'erreur setup token, pages
légales (`pageTitle`, `publisherIntro`, corps CGV articles 1/2/5/7), `subscriptionSuspended`.
Idem côté `landing/lib/i18n/translations.ts` (6 occurrences, sous-ensemble marketing).

### Metadata `<title>` codés en dur dans les pages légales (n'utilisent PAS BRAND_NAME)
- `frontend/app/(legal)/mentions-legales/page.tsx:3`
- `frontend/app/(legal)/politique-confidentialite/page.tsx:3`
- `frontend/app/(legal)/cgv/page.tsx:3`

**Vérifié** : la « raison sociale » de l'entité légale est encore un placeholder
`[À COMPLÉTER]` partout (DPA.md, mentions légales) — "SmartTicket" y est utilisé uniquement
comme **nom commercial du service**, jamais comme raison sociale enregistrée. Donc **pas
d'ambiguïté juridique** : ces occurrences sont bien catégorie (a), y compris dans `DPA.md`
(13 occurrences, ex. `DPA.md:1`, `DPA.md:20`).

### Emails transactionnels
- `ops/notify.py:39-65` — sujet, corps, `sender.name`
- `backend/email_utils.py:22,32,80-124` — `sender.name`, corps des 3 emails (confirmation,
  bienvenue, reset password)
- `backend/notifications.py:38-40` — notif réponse SAV
- `backend/main.py:347` — message "service suspendu"
- `backend/routers/auth.py:238` — message token expiré

### PDF exports (visible client)
- `backend/pdf_export.py:29,81,132,173` — pied de page + titres rapports

### Fichiers de tests qui assertent sur ces textes UI (doivent suivre en même temps, sinon
ils cassent)
- `frontend/__tests__/OnboardingModal.test.tsx` (5x "Bienvenue sur SmartTicket")
- `frontend/__tests__/AiDisclosure.test.tsx:36`

### README public / vitrine
- `README.md:1,3,7`, `landing/README.md:1` (mais ce dernier mélange marque et identifiant
  technique, voir douteux)
- `INSTALLATION.MD:2`
- `docs/designs/landing-page-et-documentation-client.md` — copie marketing (document de
  planification, faible priorité)

### Divers marque visible mineurs
- `.env.example:46` — URL d'exemple en commentaire (`smartticket.exemple.com`), cosmétique
- `frontend/app/api/mistral-status/route.ts:28` — `User-Agent: "Mozilla/5.0 (compatible;
  SmartTicket/1.0)"` (identifiant HTTP sortant, pas vu par l'utilisateur mais porte la marque)

---

## (b) IDENTIFIANT TECHNIQUE → NE PAS TOUCHER

- **Nom du repo GitHub** (`Gabricode5/SmartTicket`) et toutes les URLs qui en dépendent :
  `CHANGELOG.md:54-65` (12 liens de release), `ops/provision_client.py:93` `DEFAULT_REPO`,
  docs de design. Renommer le repo casserait tous ces liens + le clone existant + les
  remotes de tous les contributeurs.
- **`render.yaml` (racine) et `landing/render.yaml`** : noms de services déjà déployés
  (`smartticket-backend`, `smartticket-frontend`, `smartticket-postgres`,
  `smartticket-landing`) et leurs URLs `.onrender.com` codées en dur (`render.yaml:2-52`,
  `.github/workflows/ci.yml:218-219` qui les affiche dans le résumé CI). Renommer romprait
  le déploiement live.
- **`backend/pyproject.toml:6`** `name = "smartticket-backend"` — métadonnée de package
  interne, jamais publiée.
- **`backend/dependencies.py:89`** `GUEST_EMAIL_DOMAIN = "@guest.smartticket.local"` —
  domaine factice `.local` jamais résolu, sert uniquement de marqueur interne pour détecter
  les comptes fantômes.
- **`.claude/settings.json:5`** — chemin Windows local (`c:\Users\gguery\...\SmartTicket\
  frontend`) d'une autre machine, sans rapport avec le repo.
- **`ops/provision_client.py:126-134`** — fonctions générant les noms de service Render pour
  **les futures instances clients**. Voir section douteuse ci-dessous.
- **Tests `ops/tests/*.py`** (`test_render_client.py`, `test_provision_rollback.py`,
  `test_fleet_admin.py`) — testent le code de `ops/provision_client.py`, suivent la même
  décision que lui.
- **ROADMAP.md** (entrées "Fait" historiques, ex. lignes 34, 131, 133-136, 171, 173, 186) —
  journal daté décrivant ce qui **a été fait à l'époque**. Réécrire ces entrées falsifierait
  l'historique. Seules les entrées "À faire" tournées vers l'avenir (domaine
  `smartticket.fr`) sont à reconsidérer — voir douteux.
- **`docs/designs/admin-custom-system-prompt.md:5`** — juste `Repo: Gabricode5/SmartTicket`.

---

## (c) DOUTEUX — à trancher avant Étape 1

1. **Convention de nommage des futures instances Render**
   (`ops/provision_client.py:126-134`, commentaires lignes 41, 171). Aujourd'hui :
   `smartticket-{slug}-{suffix}-backend`. Les instances déjà provisionnées ne bougent pas
   (catégorie b, confirmé). Mais pour les nouveaux clients à partir de maintenant, faut-il
   générer `tiqia-{slug}-...` ? Touche le code de provisioning + tous les tests qui
   assertent ce format.

2. **Domaine email/sous-domaine `smartticket.fr`** — encore un TODO non réalisé dans le
   ROADMAP (jamais acheté). Plusieurs endroits l'anticipent : `ops/provision_client.py:99`
   `DEFAULT_SENDER_DOMAIN`, `ops/README.md:53`, ROADMAP.md lignes 137/223/224. Quelle
   extension exacte a été achetée pour `tiqia` (`.fr`, `.com`, `.app`...) ? Conditionne
   SPF/DKIM/DMARC et les futurs sous-domaines par client.

3. **Emails de fallback codés en dur** : `admin@smartticket.app` (`backend/main.py:191`,
   `backend/tests/test_admin_setup.py:15`), `no-reply@smartticket.app`
   (`backend/email_utils.py:22`). Domaine `.app`, jamais confirmé comme domaine réel en
   prod (ADMIN_EMAIL/SMTP_FROM sont `sync: false` sur Render, donc fallback dev/tests
   uniquement).

4. **`landing/package.json:2`** `"name": "smartticket-landing"` — nom du package npm local
   (jamais publié). Zéro impact fonctionnel, rename ou pas.

5. **Fichiers image `logo_smartticket.png`** (frontend/public + landing/public, 12
   références dans le code) — c'est le logo visuel réel, pas juste du texte. Renommer le
   fichier est trivial, mais le **contenu visuel** doit être remplacé par un logo Tiqia —
   asset à fournir. `frontend/public/SmartTicket_logo_32px.png` semble orphelin (aucune
   référence trouvée) — à confirmer avant suppression.

6. **`favicon.ico`** (`frontend/app/favicon.ico`) — jamais touché lors du dernier passage
   logo. Pour un rebrand complet, à régénérer aussi — asset à fournir.

7. **Liste de mots de passe faibles interdits** — `backend/routers/auth.py:196` bloque
   `"smartticket"`. Cohérence voudrait qu'on ajoute `"tiqia"`.

8. **`GUEST_EMAIL_DOMAIN = "@guest.smartticket.local"`** — renommable sans risque, mais
   cosmétique interne uniquement.

9. **`landing/README.md:1,9`** — mélange nom de marque (titre) et URL technique déjà live
   (`smartticket-frontend.onrender.com`, catégorie b) dans le même fichier.

---

## Risques de casse build/déploiement si mal fait

1. **`frontend/Dockerfile:14-15`** déclare déjà `ARG NEXT_PUBLIC_BRAND_NAME` correctement —
   ne pas y toucher. Le piège documenté dans le Dockerfile (commentaire lignes 5-11) : toute
   variable `NEXT_PUBLIC_*` ajoutée sans `ARG` correspondant est bakée avec sa valeur par
   défaut du code source au lieu de la valeur Render (déjà arrivé une fois, 2026-08-15).
   Après avoir changé le défaut dans `brand.ts`, rien à changer côté Dockerfile — mais toute
   nouvelle var liée au rebrand devra suivre ce pattern.
2. **Root `render.yaml`** ne pose PAS `NEXT_PUBLIC_BRAND_NAME` pour le service
   `smartticket-frontend` — ce service utilisera la valeur par défaut de `brand.ts` après
   rebuild. Nécessite un rebuild/redeploy Render pour se propager (valeur bakée au build).
3. Les instances clients déjà provisionnées ont `NEXT_PUBLIC_BRAND_NAME` injecté
   explicitement par `provision_client.py` — non affectées par un changement du défaut
   (confirmé par `ops/tests/test_provision_rollback.py:562`).
4. **`landing/render.yaml`** est un service statique séparé — un changement de
   `landing/lib/brand.ts` nécessite un rebuild Render pour bakée dans le HTML statique.

---

## Plan de rename minimal proposé (Étape 1, après validation)

1. `frontend/lib/brand.ts` + `landing/lib/brand.ts` : défaut `"SmartTicket"` → `"Tiqia"`.
2. `frontend/lib/i18n/translations.ts` + `landing/lib/i18n/translations.ts` : chaînes
   marketing/légales/emails-erreur en dur (FR+EN).
3. `ops/notify.py`, `backend/email_utils.py`, `backend/notifications.py`, `backend/main.py`,
   `backend/routers/auth.py` (message token expiré), `backend/pdf_export.py`.
4. 3 `<title>` en dur dans les pages légales.
5. Tests qui assertent le texte UI (`OnboardingModal.test.tsx`, `AiDisclosure.test.tsx`) —
   même commit que le point 2, sinon build rouge.
6. Assets logo/favicon — bloqué en attente du nouveau visuel Tiqia.
7. Rien touché côté `render.yaml`, `landing/render.yaml`, noms de services, `DEFAULT_REPO`,
   `pyproject.toml`, CI, CHANGELOG.

Points 1 (convention de nommage future) et 2 (domaine réel `tiqia.xxx`) de la section
douteuse restent à trancher avant d'attaquer `ops/provision_client.py` — le reste peut
démarrer indépendamment.
