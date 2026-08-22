// NEXT_PUBLIC_* est bakée au BUILD Next.js, jamais réévaluée au runtime (rewrites(),
// redirects() et les env vars NEXT_PUBLIC_* sont figées dans le bundle par `next build`,
// cf. NEXT_PUBLIC_API_URL/FRONTEND_URL dans ops/provision_client.py pour le même piège) —
// BRAND_NAME doit donc être posée AVANT le build de chaque instance, jamais après.
export const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME || "Tiqia";
