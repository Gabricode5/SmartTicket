// NEXT_PUBLIC_* est bakée au BUILD Next.js, jamais réévaluée au runtime — voir la
// même remarque dans le frontend principal (lib/brand.ts).
export const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME || "Tiqia";

// URL de l'app principale (frontend/backend complet) vers laquelle pointent les CTA
// (login, sign-up, chat). Les pages légales (mentions-legales/politique-confidentialite/cgv)
// sont servies localement par cette landing depuis le 2026-08-25 (identifient l'entité
// Tiqia elle-même, pas une instance client — n'ont donc pas leur place sur frontend/).
export const APP_URL = (
  process.env.NEXT_PUBLIC_APP_URL || "https://smartticket-frontend.onrender.com"
).replace(/\/$/, "");

// Domaine propre de CETTE landing (tiqia.fr), contrairement à APP_URL ci-dessus qui vise
// l'app cliente. Pas de variable d'env ici : à la différence de frontend/ (une instance par
// client, domaine variable), cette landing est un site unique avec un seul domaine réel —
// utilisé par robots.ts/sitemap.ts pour construire des URLs absolues correctes.
export const SITE_URL = "https://tiqia.fr";
