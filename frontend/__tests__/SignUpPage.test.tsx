import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SignUpPage from "@/app/(auth)/sign-up/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/prénom/i), { target: { value: "Jean" } });
  fireEvent.change(screen.getByLabelText(/^nom$/i), { target: { value: "Dupont" } });
  fireEvent.change(screen.getByLabelText(/nom d'utilisateur/i), { target: { value: "jean_dupont" } });
  fireEvent.change(screen.getByLabelText(/adresse email/i), { target: { value: "jean@example.com" } });
  fireEvent.change(screen.getByLabelText(/^mot de passe$/i), { target: { value: "password123" } });
  fireEvent.change(screen.getByLabelText(/confirmer le mot de passe/i), { target: { value: "password123" } });
  fireEvent.click(screen.getByLabelText(/j'accepte/i));
}

describe("SignUpPage", () => {
  it("shows a check-your-email screen instead of redirecting after registration", async () => {
    mockFetch(() => jsonResponse({ id: 1, email: "jean@example.com", email_verified: false }, 201));

    render(<SignUpPage />);
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /créer mon compte/i }));

    expect(await screen.findByText(/vérifiez votre boîte mail/i)).toBeInTheDocument();
    expect(screen.getByText("jean@example.com")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /créer mon compte/i })).not.toBeInTheDocument();
  });

  it("shows the server error and stays on the form when registration fails", async () => {
    mockFetch(() => jsonResponse({ detail: "Cet email est déjà utilisé." }, 400));

    render(<SignUpPage />);
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /créer mon compte/i }));

    await waitFor(() => {
      expect(screen.getByText("Cet email est déjà utilisé.")).toBeInTheDocument();
    });
    expect(screen.queryByText(/vérifiez votre boîte mail/i)).not.toBeInTheDocument();
  });
});
