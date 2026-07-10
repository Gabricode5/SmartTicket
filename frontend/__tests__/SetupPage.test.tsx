import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SetupPage from "@/app/(auth)/setup/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

let searchParams = new URLSearchParams();
jest.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

const VALID_PASSWORD = "AcmeAdmin2026x";

function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText(/nom d'utilisateur/i), { target: { value: "acme_admin" } });
  fireEvent.change(screen.getByLabelText(/adresse email/i), { target: { value: "admin@acme.com" } });
  fireEvent.change(screen.getByLabelText(/^mot de passe$/i), { target: { value: VALID_PASSWORD } });
  fireEvent.change(screen.getByLabelText(/confirmer le mot de passe/i), { target: { value: VALID_PASSWORD } });
  fireEvent.click(screen.getByRole("button", { name: /configurer mon compte/i }));
}

describe("SetupPage", () => {
  beforeEach(() => {
    searchParams = new URLSearchParams();
    searchParams.set("token", "valid-token");
  });

  it("completes setup and shows a success screen", async () => {
    const fetchMock = mockFetch(() => jsonResponse({ message: "ok" }));

    render(<SetupPage />);
    fillAndSubmit();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/setup",
        expect.objectContaining({
          body: JSON.stringify({ token: "valid-token", username: "acme_admin", email: "admin@acme.com", password: VALID_PASSWORD }),
        })
      );
    });
    expect(await screen.findByText(/configuration terminée/i)).toBeInTheDocument();
  });

  it("shows a mismatch error and does not submit when passwords differ", async () => {
    const fetchMock = mockFetch(() => jsonResponse({ message: "ok" }));

    render(<SetupPage />);
    fireEvent.change(screen.getByLabelText(/nom d'utilisateur/i), { target: { value: "acme_admin" } });
    fireEvent.change(screen.getByLabelText(/adresse email/i), { target: { value: "admin@acme.com" } });
    fireEvent.change(screen.getByLabelText(/^mot de passe$/i), { target: { value: VALID_PASSWORD } });
    fireEvent.change(screen.getByLabelText(/confirmer le mot de passe/i), { target: { value: "different4567890" } });
    fireEvent.click(screen.getByRole("button", { name: /configurer mon compte/i }));

    expect((await screen.findAllByText(/ne correspondent pas/i)).length).toBeGreaterThan(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects a password under 12 characters client-side without submitting", async () => {
    const fetchMock = mockFetch(() => jsonResponse({ message: "ok" }));

    render(<SetupPage />);
    fireEvent.change(screen.getByLabelText(/nom d'utilisateur/i), { target: { value: "acme_admin" } });
    fireEvent.change(screen.getByLabelText(/adresse email/i), { target: { value: "admin@acme.com" } });
    fireEvent.change(screen.getByLabelText(/^mot de passe$/i), { target: { value: "short11char" } });
    fireEvent.change(screen.getByLabelText(/confirmer le mot de passe/i), { target: { value: "short11char" } });
    fireEvent.click(screen.getByRole("button", { name: /configurer mon compte/i }));

    expect(await screen.findByText(/doit contenir au moins 12 caractères/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ["invalid_token", /lien de configuration est invalide/i],
    ["token_already_used", /déjà été utilisé/i],
    ["token_expired", /a expiré/i],
  ])("shows a dedicated message for the %s error state", async (code, expectedText) => {
    mockFetch(() => jsonResponse({ detail: { code, message: "server message" } }, 400));

    render(<SetupPage />);
    fillAndSubmit();

    expect(await screen.findByText(expectedText)).toBeInTheDocument();
  });

  it("shows a generic server error (e.g. duplicate email) inline instead of the token screen", async () => {
    mockFetch(() => jsonResponse({ detail: "Cet email est déjà utilisé." }, 400));

    render(<SetupPage />);
    fillAndSubmit();

    expect(await screen.findByText("Cet email est déjà utilisé.")).toBeInTheDocument();
    expect(screen.queryByText(/lien indisponible/i)).not.toBeInTheDocument();
  });

  it("shows the invalid-token screen immediately when no token is present in the URL", async () => {
    searchParams = new URLSearchParams();

    render(<SetupPage />);
    fillAndSubmit();

    expect(await screen.findByText(/lien de configuration est invalide/i)).toBeInTheDocument();
  });
});
