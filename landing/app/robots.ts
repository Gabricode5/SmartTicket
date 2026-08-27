import type { MetadataRoute } from "next"
import { SITE_URL } from "@/lib/brand"

// Site vitrine public (tiqia.fr) : indexation autorisée, à l'inverse de frontend/ (instances
// client, jamais indexées — cf. frontend/app/robots.ts).
//
// export const dynamic = "force-static" explicite requis avec output: "export" (même raison
// que sitemap.ts, cf. son commentaire — confirmé par un vrai build en échec sans cette ligne).
export const dynamic = "force-static"

export default function robots(): MetadataRoute.Robots {
    return {
        rules: {
            userAgent: "*",
            allow: "/",
        },
        sitemap: `${SITE_URL}/sitemap.xml`,
    }
}
