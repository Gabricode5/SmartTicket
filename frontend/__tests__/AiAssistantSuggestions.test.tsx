import { render, screen } from "@testing-library/react";
import AiAssistantPage from "@/app/(chat)/ai-assistant/[id]/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

jest.mock("next/navigation", () => ({
  useParams: () => ({ id: "7" }),
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}));

jest.mock("streamdown", () => ({
  Streamdown: ({ children }: { children: string }) => children,
}), { virtual: true });

Element.prototype.scrollIntoView = jest.fn();

const apiUser = { id: 1, username: "gabriel", email: "gabriel@example.com", role: "user" };

describe("AiAssistantPage — suggestions de démarrage", () => {
  it("shows generic, business-agnostic starter suggestions instead of the old Stripe-specific ones", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(apiUser);
      if (url.startsWith("/api/messages?session_id=")) return jsonResponse([]);
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse([{ id: 7, status: "open", has_sav_reply: false }]);
      return jsonResponse({}, 404);
    });

    render(<AiAssistantPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Suivre ma commande")).toBeInTheDocument();
    expect(screen.getByText("Retour ou remboursement")).toBeInTheDocument();
    expect(screen.getByText("Contacter un agent")).toBeInTheDocument();
    expect(screen.getByText("Mon compte")).toBeInTheDocument();

    expect(screen.queryByText(/stripe/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/cvv/i)).not.toBeInTheDocument();
  });
});
