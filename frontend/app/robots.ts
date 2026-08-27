import type { MetadataRoute } from "next"

// Instances client (données personnelles, contenu confidentiel par tenant) : indexation
// interdite sur TOUTE l'instance, à l'inverse de landing/ (tiqia.fr, vitrine publique — cf.
// landing/app/robots.ts). Pas de sitemap ici, volontairement — rien à indexer.
export default function robots(): MetadataRoute.Robots {
    return {
        rules: {
            userAgent: "*",
            disallow: "/",
        },
    }
}
