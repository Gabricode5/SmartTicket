import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { GuestClaimBanner } from "@/components/GuestClaimBanner";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

describe("GuestClaimBanner", () => {
  it("shows the invite banner by default", () => {
    render(<GuestClaimBanner />);
    expect(screen.getByText(/conversation anonyme/i)).toBeInTheDocument();
  });

  it("opens the claim form and submits it", async () => {
    const fetchMock = mockFetch(() => jsonResponse({ email: "me@example.com", is_guest: false }));

    render(<GuestClaimBanner />);
    fireEvent.click(screen.getByRole("button", { name: /créer un compte/i }));

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "me@example.com" } });
    fireEvent.change(screen.getByLabelText(/mot de passe/i), { target: { value: "a-real-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: /valider/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/me/claim",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ email: "me@example.com", password: "a-real-password-123" }),
        })
      );
    });
    expect(await screen.findByText(/compte créé/i)).toBeInTheDocument();
  });

  it("shows the server error when claiming fails", async () => {
    mockFetch(() => jsonResponse({ detail: "Cet email est déjà utilisé" }, 400));

    render(<GuestClaimBanner />);
    fireEvent.click(screen.getByRole("button", { name: /créer un compte/i }));
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "taken@example.com" } });
    fireEvent.change(screen.getByLabelText(/mot de passe/i), { target: { value: "a-real-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: /valider/i }));

    expect(await screen.findByText("Cet email est déjà utilisé")).toBeInTheDocument();
  });
});
