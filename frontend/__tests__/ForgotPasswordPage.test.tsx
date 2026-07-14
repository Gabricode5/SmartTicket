import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ForgotPasswordPage from "@/app/(auth)/forgot-password/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

describe("ForgotPasswordPage", () => {
  it("shows a check-your-email confirmation after submitting", async () => {
    const fetchMock = mockFetch(() => jsonResponse({ message: "ok" }));

    render(<ForgotPasswordPage />, { wrapper: LocaleProvider });
    fireEvent.change(screen.getByLabelText(/adresse email/i), { target: { value: "me@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /envoyer le lien/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/forgot-password",
        expect.objectContaining({ body: JSON.stringify({ email: "me@example.com" }) })
      );
    });
    expect(await screen.findByText(/vérifiez votre boîte mail/i)).toBeInTheDocument();
  });

  it("shows an error if the request fails", async () => {
    mockFetch(() => jsonResponse({}, 500));

    render(<ForgotPasswordPage />, { wrapper: LocaleProvider });
    fireEvent.change(screen.getByLabelText(/adresse email/i), { target: { value: "me@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /envoyer le lien/i }));

    expect(await screen.findByText(/impossible d'envoyer le lien/i)).toBeInTheDocument();
    expect(screen.queryByText(/vérifiez votre boîte mail/i)).not.toBeInTheDocument();
  });
});
