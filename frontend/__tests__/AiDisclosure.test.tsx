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

// Obligation de transparence IA (règlement européen sur l'IA, art. 50) : la personne qui
// démarre une conversation doit être informée qu'elle échange avec un système d'IA — cf.
// lib/i18n/translations.ts (chat.aiDisclosure) et l'écran d'accueil de ai-assistant/[id].
// Vérifie AUSSI qu'aucune marque de LLM (Mistral) ne fuite vers cette surface visible par
// le public final d'un client — distinct de la séparation vitrine/instance (proxy.test.ts),
// qui masque la landing mais ne garantit pas à elle seule l'absence de "Mistral" DANS le chat.
describe("AiAssistantPage — transparence IA (art. 50)", () => {
  it("shows an AI disclosure notice mentioning the brand name, before the first message", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(apiUser);
      if (url.startsWith("/api/messages?session_id=")) return jsonResponse([]);
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse([{ id: 7, status: "open", has_sav_reply: false }]);
      return jsonResponse({}, 404);
    });

    render(<AiAssistantPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText(/échangez avec l'assistant IA de SmartTicket/i)).toBeInTheDocument();
  });

  it("never mentions Mistral anywhere on the chat screen end-users actually see", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(apiUser);
      if (url.startsWith("/api/messages?session_id=")) return jsonResponse([]);
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse([{ id: 7, status: "open", has_sav_reply: false }]);
      return jsonResponse({}, 404);
    });

    render(<AiAssistantPage />, { wrapper: LocaleProvider });

    await screen.findByText(/échangez avec l'assistant IA/i);
    expect(screen.queryByText(/mistral/i)).not.toBeInTheDocument();
  });
});
