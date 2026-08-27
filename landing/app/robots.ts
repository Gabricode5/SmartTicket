import type { MetadataRoute } from "next"
import { SITE_URL } from "@/lib/brand"

// Site vitrine public (tiqia.fr) : indexation autorisée, à l'inverse de frontend/ (instances
// client, jamais indexées — cf. frontend/app/robots.ts). Route statique par défaut sous
// output: "export" (aucune API dynamique utilisée ici) — génère un vrai robots.txt dans out/.
export default function robots(): MetadataRoute.Robots {
    return {
        rules: {
            userAgent: "*",
            allow: "/",
        },
        sitemap: `${SITE_URL}/sitemap.xml`,
    }
}
