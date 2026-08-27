import type { MetadataRoute } from "next"
import { SITE_URL } from "@/lib/brand"

// Pages publiques uniquement — /chat, /login etc. n'existent pas sur cette landing statique
// (cf. lib/brand.ts::APP_URL, ils vivent sur l'instance frontend/ du client). Route statique
// par défaut sous output: "export" (aucune API dynamique utilisée ici) — génère un vrai
// sitemap.xml dans out/.
export default function sitemap(): MetadataRoute.Sitemap {
    return [
        {
            url: SITE_URL,
            changeFrequency: "weekly",
            priority: 1,
        },
        {
            url: `${SITE_URL}/mentions-legales`,
            changeFrequency: "yearly",
            priority: 0.3,
        },
        {
            url: `${SITE_URL}/politique-confidentialite`,
            changeFrequency: "yearly",
            priority: 0.3,
        },
        {
            url: `${SITE_URL}/cgv`,
            changeFrequency: "yearly",
            priority: 0.3,
        },
    ]
}
