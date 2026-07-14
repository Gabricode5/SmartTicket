import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import AiAssistantPage from "@/app/(chat)/ai-assistant/[id]/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

jest.mock("next/navigation", () => ({
  useParams: () => ({ id: "7" }),
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}));

// streamdown is ESM-only (no CJS "require" export condition) and unresolvable under
// Jest's default CJS transform — mocked here rather than touching the shared Jest config.
jest.mock("streamdown", () => ({
  Streamdown: ({ children }: { children: string }) => children,
}), { virtual: true });

// jsdom does not implement scrollIntoView; the page calls it on every message update.
Element.prototype.scrollIntoView = jest.fn();

const apiUser = { id: 1, username: "gabriel", email: "gabriel@example.com", role: "user" };

const messages = [
  { id: 1, type_envoyeur: "user", contenu: "J'ai un souci.", date_creation: "2026-01-01T10:00:00Z" },
  { id: 2, type_envoyeur: "sav", contenu: "Voici la solution.", date_creation: "2026-01-01T10:05:00Z" },
];

function sessionsResponse(overrides: Partial<{ status: string; has_sav_reply: boolean }>) {
  return jsonResponse([{ id: 7, status: "transferred", has_sav_reply: false, ...overrides }]);
}

describe("AiAssistantPage — reprise de la main par l'IA", () => {
  it("shows the resume button once the SAV has replied and lets the client resume", async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url === "/api/me") return jsonResponse(apiUser);
      if (url.startsWith("/api/messages?session_id=")) return jsonResponse(messages);
      if (url.startsWith("/api/sessions?user_id=")) return sessionsResponse({ has_sav_reply: true });
      if (url === "/api/sessions/7/resolve" && init?.method === "POST") return jsonResponse({ id: 7, status: "open" });
      return jsonResponse({}, 404);
    });

    render(<AiAssistantPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Un agent SAV a répondu à votre demande.")).toBeInTheDocument();
    const resumeButton = screen.getByRole("button", { name: /reprendre avec l'ia/i });

    fireEvent.click(resumeButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/sessions/7/resolve", { method: "POST" });
    });
    await waitFor(() => {
      expect(screen.queryByText("Un agent SAV a répondu à votre demande.")).not.toBeInTheDocument();
    });
  });

  it("does not show the resume button while still waiting for a SAV reply", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(apiUser);
      if (url.startsWith("/api/messages?session_id=")) return jsonResponse([]);
      if (url.startsWith("/api/sessions?user_id=")) return sessionsResponse({ has_sav_reply: false });
      return jsonResponse({}, 404);
    });

    render(<AiAssistantPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("En attente d'un agent SAV — un agent humain va vous répondre prochainement.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reprendre avec l'ia/i })).not.toBeInTheDocument();
  });
});
