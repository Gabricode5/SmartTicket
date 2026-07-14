import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import VerifyEmailPage from "@/app/(auth)/verify-email/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

let searchParams = new URLSearchParams();
jest.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    searchParams = new URLSearchParams();
  });

  it("shows a success message when the token is valid", async () => {
    searchParams.set("token", "valid-token");
    mockFetch((url) => {
      expect(url).toBe("/api/verify-email?token=valid-token");
      return jsonResponse({ message: "Adresse email vérifiée avec succès." });
    });

    render(<VerifyEmailPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText(/email vérifié/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /se connecter/i })).toHaveAttribute("href", "/login");
  });

  it("shows an error and a resend form when the token is invalid", async () => {
    searchParams.set("token", "expired-token");
    const fetchMock = mockFetch((url) => {
      if (url.startsWith("/api/verify-email")) return jsonResponse({ detail: "Lien de vérification invalide ou expiré" }, 400);
      return jsonResponse({ message: "ok" });
    });

    render(<VerifyEmailPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Lien de vérification invalide ou expiré")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/recevoir un nouveau lien/i), { target: { value: "me@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /renvoyer le lien/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/resend-verification",
        expect.objectContaining({ body: JSON.stringify({ email: "me@example.com" }) })
      );
    });
    expect(await screen.findByText(/nouveau lien vient d'être envoyé/i)).toBeInTheDocument();
  });

  it("shows an error immediately when there is no token in the URL", async () => {
    render(<VerifyEmailPage />, { wrapper: LocaleProvider });
    expect(await screen.findByText("Lien de vérification invalide.")).toBeInTheDocument();
  });
});
