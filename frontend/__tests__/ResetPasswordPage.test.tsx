import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ResetPasswordPage from "@/app/(auth)/reset-password/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

let searchParams = new URLSearchParams();
jest.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    searchParams = new URLSearchParams();
    searchParams.set("token", "valid-token");
  });

  it("resets the password and shows a success screen", async () => {
    const fetchMock = mockFetch(() => jsonResponse({ message: "ok" }));

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/nouveau mot de passe/i), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText(/confirmer le mot de passe/i), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: /réinitialiser le mot de passe/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/reset-password",
        expect.objectContaining({ body: JSON.stringify({ token: "valid-token", new_password: "password123" }) })
      );
    });
    expect(await screen.findByText(/mot de passe réinitialisé/i)).toBeInTheDocument();
  });

  it("shows a mismatch error and does not submit when passwords differ", async () => {
    const fetchMock = mockFetch(() => jsonResponse({ message: "ok" }));

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/nouveau mot de passe/i), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText(/confirmer le mot de passe/i), { target: { value: "different456" } });
    fireEvent.click(screen.getByRole("button", { name: /réinitialiser le mot de passe/i }));

    // Le champ affiche déjà un indicateur en direct dès que les valeurs diffèrent, en plus
    // du message d'erreur posté à la soumission — les deux partagent le même texte.
    expect((await screen.findAllByText(/ne correspondent pas/i)).length).toBeGreaterThan(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the server error when the token is invalid or expired", async () => {
    mockFetch(() => jsonResponse({ detail: "Lien de réinitialisation invalide ou expiré" }, 400));

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/nouveau mot de passe/i), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText(/confirmer le mot de passe/i), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: /réinitialiser le mot de passe/i }));

    expect(await screen.findByText("Lien de réinitialisation invalide ou expiré")).toBeInTheDocument();
  });
});
