import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SettingsPage from "@/app/(dashboard)/settings/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
}));

const baseMe = {
  id: 1,
  username: "alice",
  email: "alice@example.com",
  prenom: "Alice",
  nom: "Dupont",
  role: "user",
  email_verified: true,
  date_creation: "2026-01-01T00:00:00Z",
};

describe("SettingsPage — email verification banner", () => {
  it("shows nothing when the email is already verified", async () => {
    mockFetch((url) => (url === "/api/me" ? jsonResponse(baseMe) : jsonResponse({}, 404)));

    render(<SettingsPage />, { wrapper: LocaleProvider });
    await screen.findByDisplayValue("alice@example.com");
    expect(screen.queryByText(/confirmez votre nouvelle adresse/i)).not.toBeInTheDocument();
  });

  it("shows a banner with a resend button when the email is unverified", async () => {
    mockFetch((url) =>
      url === "/api/me" ? jsonResponse({ ...baseMe, email_verified: false }) : jsonResponse({}, 404)
    );

    render(<SettingsPage />, { wrapper: LocaleProvider });
    expect(await screen.findByText(/confirmez votre nouvelle adresse/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /renvoyer l'email/i })).toBeInTheDocument();
  });

  it("resends the verification email and confirms it was sent", async () => {
    const fetchMock = mockFetch((url) =>
      url === "/api/me"
        ? jsonResponse({ ...baseMe, email_verified: false })
        : url === "/api/resend-verification"
          ? jsonResponse({ message: "ok" })
          : jsonResponse({}, 404)
    );

    render(<SettingsPage />, { wrapper: LocaleProvider });
    fireEvent.click(await screen.findByRole("button", { name: /renvoyer l'email/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/resend-verification",
        expect.objectContaining({ body: JSON.stringify({ email: "alice@example.com" }) })
      );
    });
    expect(await screen.findByText(/email renvoyé/i)).toBeInTheDocument();
  });

  it("shows the banner right after saving a profile that resets email_verified to false", async () => {
    mockFetch((url, init) => {
      if (url === "/api/me" && (!init || !init.method)) return jsonResponse(baseMe);
      if (url === "/api/me" && init?.method === "PUT") {
        return jsonResponse({ ...baseMe, email: "new@example.com", email_verified: false });
      }
      return jsonResponse({}, 404);
    });

    render(<SettingsPage />, { wrapper: LocaleProvider });
    await screen.findByDisplayValue("alice@example.com");
    expect(screen.queryByText(/confirmez votre nouvelle adresse/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /enregistrer le profil/i }));

    expect(await screen.findByText(/confirmez votre nouvelle adresse/i)).toBeInTheDocument();
  });
});
