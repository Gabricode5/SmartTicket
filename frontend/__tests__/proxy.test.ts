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
  it.each(["/", "/login", "/sign-up", "/forgot-password", "/verify-email", "/reset-password", "/chat", "/mentions-legales", "/politique-confidentialite", "/cgv"])(
    "allows unauthenticated access to the public path %s",
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
