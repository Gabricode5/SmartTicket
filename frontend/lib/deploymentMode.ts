// Même piège de timing que BRAND_NAME (cf. lib/brand.ts) : NEXT_PUBLIC_* est bakée au BUILD,
// jamais réévaluée au runtime — DEPLOYMENT_MODE doit être posée AVANT le build.
//
// Défaut delibérément "instance", à l'INVERSE de BRAND_NAME (qui défaut à "SmartTicket",
// donc au site vitrine) : si cette variable est omise par erreur sur une vraie instance
// cliente, l'erreur doit se traduire par "pas de marketing/marque LLM visible", jamais par
// une fuite de la landing SmartTicket vers le public d'un client (secteur régulé — cf.
// ROADMAP.md, chantier "séparer le site vitrine de l'instance client", 2026-08-15).
export const DEPLOYMENT_MODE = process.env.NEXT_PUBLIC_DEPLOYMENT_MODE === "marketing" ? "marketing" : "instance";

export const IS_MARKETING_SITE = DEPLOYMENT_MODE === "marketing";
