import type { MetadataRoute } from "next"
import { SITE_URL } from "@/lib/brand"

// Pages publiques uniquement — /chat, /login etc. n'existent pas sur cette landing statique
// (cf. lib/brand.ts::APP_URL, ils vivent sur l'instance frontend/ du client).
//
// export const dynamic = "force-static" est OBLIGATOIRE ici avec output: "export" (2026-08-27) :
// contrairement à ce qu'on pouvait attendre de la présence de `force-static` dans le loader
// webpack de Next.js pour les routes metadata, le build échoue sans cette déclaration explicite
// dans le fichier utilisateur lui-même — confirmé par un vrai build en échec, pas supposé.
export const dynamic = "force-static"

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
