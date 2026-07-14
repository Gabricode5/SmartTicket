#!/usr/bin/env node
// Vérifie, juste après `next build`, deux invariants qui se sont cassés SILENCIEUSEMENT le
// 2026-07-14 sans faire échouer `next build` lui-même (le build réussit même avec
// NEXT_PUBLIC_API_URL vide/absente — il se contente de retomber sur le fallback localhost) :
//
//   1. Le rewrite /api/:path* (frontend/next.config.ts) pointe vers une vraie URL backend —
//      jamais localhost, jamais vide. Next.js bake ce rewrite dans routes-manifest.json AU
//      BUILD, il n'est plus jamais réévalué ensuite (ni par `next start`, ni par un
//      redeploy à chaud) : une valeur figée au mauvais moment reste fausse pour toujours,
//      jusqu'au prochain build.
//   2. La page /setup existe bien dans le build (cf. app-path-routes-manifest.json) — le
//      lien d'amorçage du compte admin envoyé par ops/provision_client.py doit rester
//      servi.
//
// Lancé en CI juste après `npm run build` (cf. .github/workflows/ci.yml). Si l'un des deux
// échoue, la CI échoue avec un message explicite plutôt que de laisser un build "réussi"
// silencieusement casser le provisioning en production.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const buildDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", ".next");

function readJson(name) {
    return JSON.parse(readFileSync(path.join(buildDir, name), "utf-8"));
}

let failed = false;

function fail(message) {
    console.error(`✗ ${message}`);
    failed = true;
}

function ok(message) {
    console.log(`✓ ${message}`);
}

// --- 1. Rewrite /api/:path* ---
const routesManifest = readJson("routes-manifest.json");
const apiRewrite = (routesManifest.rewrites?.afterFiles ?? routesManifest.rewrites ?? [])
    .find?.((r) => r.source === "/api/:path*");

if (!apiRewrite) {
    fail("Aucun rewrite /api/:path* trouvé dans routes-manifest.json (next.config.ts a-t-il changé ?).");
} else if (!apiRewrite.destination || apiRewrite.destination.includes("localhost")) {
    fail(
        `Le rewrite /api/* pointe vers "${apiRewrite.destination}" — NEXT_PUBLIC_API_URL était ` +
        "vide ou absente au moment du build (fallback localhost figé dans l'image). " +
        "Tous les appels /api/* échoueront en production."
    );
} else {
    ok(`Rewrite /api/* -> ${apiRewrite.destination}`);
}

// --- 2. Route /setup présente ---
const appRoutes = readJson("app-path-routes-manifest.json");
const hasSetupRoute = Object.values(appRoutes).includes("/setup");

if (!hasSetupRoute) {
    fail("La route /setup est absente du build (app-path-routes-manifest.json) — le lien d'amorçage admin ne sera pas servi.");
} else {
    ok("Route /setup présente dans le build.");
}

if (failed) {
    console.error("\nÉchec de la vérification post-build — voir les messages ci-dessus.");
    process.exit(1);
}

console.log("\nVérification post-build OK.");
