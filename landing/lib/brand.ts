// NEXT_PUBLIC_* est bakée au BUILD Next.js, jamais réévaluée au runtime — voir la
// même remarque dans le frontend principal (lib/brand.ts).
export const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME || "Tiqia";

// Domaine propre de CETTE landing (tiqia.fr). Pas de variable d'env ici : à la différence
// de frontend/ (une instance par client, domaine variable), cette landing est un site unique
// avec un seul domaine réel — utilisé par robots.ts/sitemap.ts pour construire des URLs
// absolues correctes.
//
// Les pages légales (mentions-legales/politique-confidentialite/cgv) sont servies localement
// par cette landing depuis le 2026-08-25 (identifient l'entité Tiqia elle-même, pas une
// instance client — n'ont donc pas leur place sur frontend/).
//
// Historique : il a existé ici une APP_URL (NEXT_PUBLIC_APP_URL) vers l'app cliente pour les
// CTA "Se connecter". Retirée le 2026-08-28 avec ces boutons — la connexion client mono-tenant
// n'a pas de destination valide depuis la landing (cf. ROADMAP, à la 1re signature). La landing
// ne garde que le CTA "Demander une démo" (mailto:contact@tiqia.fr).
export const SITE_URL = "https://tiqia.fr";
