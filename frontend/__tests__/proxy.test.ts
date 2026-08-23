/**
 * @jest-environment node
 */
// next/server's NextRequest relies on the Fetch API globals (Request/Response) that Node
// provides natively but jsdom (this project's default Jest environment) does not.
import { NextRequest } from "next/server";
import { proxy } from "@/proxy";

function makeRequest(pathname: string, hasAuthToken: boolean) {
  const url = `https://smartticket-frontend.onrender.com${pathname}`;
  const headers: Record<string, string> = hasAuthToken ? { cookie: "auth_token=faketoken" } : {};
  return new NextRequest(url, { headers });
}

describe("proxy", () => {
  // "/" est délibérément exclu de cette liste : elle reste publique du point de vue AUTH
  // (jamais redirigée vers /login), mais peut être redirigée vers /chat pour une raison
  // ORTHOGONALE (mode de déploiement instance vs vitrine, cf. describe dédié plus bas) —
  // les deux ne doivent pas être confondues dans une même assertion générique.
  it.each(["/login", "/sign-up", "/forgot-password", "/verify-email", "/reset-password", "/setup", "/chat", "/mentions-legales", "/politique-confidentialite", "/cgv"])(
    "allows unauthenticated access to the public path %s",
    (path) => {
      const response = proxy(makeRequest(path, false));
      expect(response.status).not.toBe(307);
    }
  );

  it("never redirects / to /login for auth reasons, regardless of deployment mode", () => {
    const response = proxy(makeRequest("/", false));
    expect(response.headers.get("location")).not.toContain("/login");
  });

  it.each(["/logo-T.png", "/favicon.ico", "/robots.txt", "/some-font.woff2"])(
    "allows unauthenticated access to any static asset path %s (extension-based, not name-based)",
    (path) => {
      const response = proxy(makeRequest(path, false));
      expect(response.status).not.toBe(307);
    }
  );

  it("redirects an unauthenticated visitor away from a protected path to /login", () => {
    const response = proxy(makeRequest("/dashboard", false));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toContain("/login");
  });

  it("redirects an authenticated user away from /login to /dashboard", () => {
    const response = proxy(makeRequest("/login", true));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toContain("/dashboard");
  });

  it("lets an authenticated user reach a protected path", () => {
    const response = proxy(makeRequest("/dashboard", true));
    expect(response.status).not.toBe(307);
  });
});

// IS_MARKETING_SITE (lib/deploymentMode.ts) est une constante lue depuis process.env au
// chargement du module — comme en production, où NEXT_PUBLIC_* est figée au build, jamais
// réévaluée au runtime (cf. lib/brand.ts). Pour tester les deux valeurs dans le même
// fichier, jest.resetModules() + require() dynamique forcent une réévaluation entre chaque
// cas, exactement comme un nouveau build avec une variable différente le ferait.
describe("proxy — deployment mode redirect on /", () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_DEPLOYMENT_MODE;
    jest.resetModules();
  });

  it("redirects / to /chat by default (no NEXT_PUBLIC_DEPLOYMENT_MODE set — safe default, cf. lib/deploymentMode.ts)", () => {
    jest.resetModules();
    const { proxy: proxyWithDefaultMode } = require("@/proxy");
    const response = proxyWithDefaultMode(makeRequest("/", false));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toContain("/chat");
  });

  it("redirects / to /chat when NEXT_PUBLIC_DEPLOYMENT_MODE=instance", () => {
    process.env.NEXT_PUBLIC_DEPLOYMENT_MODE = "instance";
    jest.resetModules();
    const { proxy: proxyInInstanceMode } = require("@/proxy");
    const response = proxyInInstanceMode(makeRequest("/", false));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toContain("/chat");
  });

  it("serves the marketing landing at / (no redirect) when NEXT_PUBLIC_DEPLOYMENT_MODE=marketing", () => {
    process.env.NEXT_PUBLIC_DEPLOYMENT_MODE = "marketing";
    jest.resetModules();
    const { proxy: proxyInMarketingMode } = require("@/proxy");
    const response = proxyInMarketingMode(makeRequest("/", false));
    expect(response.status).not.toBe(307);
  });
});
