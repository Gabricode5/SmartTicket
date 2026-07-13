import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/(auth)/login/page";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

const push = jest.fn();
const refresh = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

function renderLogin() {
  return render(<LoginPage />, { wrapper: LocaleProvider });
}

function fillAndSubmit(email: string, password: string) {
  fireEvent.change(screen.getByLabelText(/adresse email/i), { target: { value: email } });
  fireEvent.change(screen.getByLabelText(/mot de passe/i), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: /se connecter/i }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    push.mockClear();
  });

  it("logs in and redirects to the dashboard on success", async () => {
    mockFetch(() => jsonResponse({ username: "alice", user_id: 1, access_token: "tok" }));

    renderLogin();
    fillAndSubmit("alice@example.com", "correct-password");

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
    expect(localStorage.getItem("username")).toBe("alice");
  });

  it("shows a plain error for wrong credentials", async () => {
    mockFetch(() => jsonResponse({ detail: "L'email ou le mot de passe est incorrect" }, 403));

    renderLogin();
    fillAndSubmit("alice@example.com", "wrong-password");

    expect(await screen.findByText("L'email ou le mot de passe est incorrect")).toBeInTheDocument();
    expect(screen.queryByText(/renvoyer l'email/i)).not.toBeInTheDocument();
  });

  it("offers to resend the verification email when the account is unverified", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/login") {
        return jsonResponse({ detail: { code: "email_not_verified", message: "Adresse email non vérifiée." } }, 403);
      }
      return jsonResponse({ message: "ok" });
    });

    renderLogin();
    fillAndSubmit("pending@example.com", "correct-password");

    const resendButton = await screen.findByRole("button", { name: /renvoyer l'email de vérification/i });
    fireEvent.click(resendButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/resend-verification",
        expect.objectContaining({ body: JSON.stringify({ email: "pending@example.com" }) })
      );
    });
    expect(await screen.findByText(/nouveau lien vient d'être envoyé/i)).toBeInTheDocument();
  });
});
