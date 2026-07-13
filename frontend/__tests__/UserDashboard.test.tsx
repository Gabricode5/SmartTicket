import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import UserDashboard from "@/components/dashboard/UserDashboard";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

function renderDashboard(userId = 42) {
  return render(<UserDashboard userId={userId} />, { wrapper: LocaleProvider });
}

const push = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const sessions = [
  { id: 1, title: "Problème de connexion", date_creation: "2026-01-05T10:00:00Z", status: "open" },
  { id: 2, title: "Facture erronée", date_creation: "2026-01-01T10:00:00Z", status: "closed" },
];

const sessionsWithTransfer = [
  ...sessions,
  { id: 3, title: "Litige commande", date_creation: "2026-01-03T10:00:00Z", status: "transferred" },
];

beforeEach(() => {
  jest.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe("UserDashboard", () => {
  it("loads and renders the user's sessions with correct stats", async () => {
    mockFetch((url) =>
      url.startsWith("/api/sessions?user_id=") ? jsonResponse(sessions) : jsonResponse({}, 404)
    );

    renderDashboard();

    expect(await screen.findByText("Problème de connexion")).toBeInTheDocument();
    expect(screen.getByText("Facture erronée")).toBeInTheDocument();

    // 2 total, 1 closed -> 50% closure rate, 1 open
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("shows an empty state when the user has no sessions", async () => {
    mockFetch(() => jsonResponse([]));

    renderDashboard();

    expect(await screen.findByText("Aucune conversation.")).toBeInTheDocument();
  });

  it("shows a session-expired error on 401", async () => {
    mockFetch(() => jsonResponse({}, 401));

    renderDashboard();

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
  });

  it("performs a debounced server-side search and highlights the match", async () => {
    const searchResults = [
      {
        id: 2,
        title: "Facture erronée",
        date_creation: "2026-01-01T10:00:00Z",
        status: "closed",
        snippet: "remboursement de la <b>facture</b> incorrecte",
      },
    ];
    const fetchMock = mockFetch((url) => {
      if (url.startsWith("/api/sessions/search")) return jsonResponse(searchResults);
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse(sessions);
      return jsonResponse({}, 404);
    });

    renderDashboard();
    await screen.findByText("Problème de connexion");

    fireEvent.change(screen.getByPlaceholderText("Rechercher des conversations..."), {
      target: { value: "facture" },
    });

    // The fetch itself is debounced (300ms), so it shouldn't fire immediately.
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining("/api/sessions/search"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/sessions/search?user_id=42&q=facture");
    });

    expect(await screen.findByText("Facture erronée")).toBeInTheDocument();
    expect(screen.queryByText("Problème de connexion")).not.toBeInTheDocument();
    // The snippet's <b>facture</b> must render as a real element, not raw HTML text.
    expect(screen.getByText("facture", { selector: "strong" })).toBeInTheDocument();
  });

  it("shows an empty-results message when the search has no matches", async () => {
    const fetchMock = mockFetch((url) => {
      if (url.startsWith("/api/sessions/search")) return jsonResponse([]);
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse(sessions);
      return jsonResponse({}, 404);
    });

    renderDashboard();
    await screen.findByText("Problème de connexion");

    fireEvent.change(screen.getByPlaceholderText("Rechercher des conversations..."), {
      target: { value: "introuvable" },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/sessions/search?user_id=42&q=introuvable");
    });
    expect(await screen.findByText("Aucun résultat pour « introuvable ».")).toBeInTheDocument();
  });

  it("closes an open session after confirmation and refreshes the list", async () => {
    const fetchMock = mockFetch((url) => {
      if (url.includes("/close")) return jsonResponse({});
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse(sessions);
      return jsonResponse({}, 404);
    });

    renderDashboard();
    await screen.findByText("Problème de connexion");

    const closeButtons = screen.getAllByRole("button", { name: "Clôturer" });
    const enabledButton = closeButtons.find((btn) => !btn.hasAttribute("disabled"));
    expect(enabledButton).toBeDefined();

    fireEvent.click(enabledButton!);

    expect(window.confirm).toHaveBeenCalledWith("Clôturer la session #1 ?");
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/sessions/1/close", { method: "POST" });
    });
  });

  it("filters conversations by status", async () => {
    mockFetch((url) =>
      url.startsWith("/api/sessions?user_id=") ? jsonResponse(sessionsWithTransfer) : jsonResponse({}, 404)
    );

    renderDashboard();
    await screen.findByText("Problème de connexion");

    // Filter tabs: 1 open, 1 transferred, 1 closed.
    expect(screen.getByText("Ouvertes (1)")).toBeInTheDocument();
    expect(screen.getByText("Transférées (1)")).toBeInTheDocument();
    expect(screen.getByText("Clôturées (1)")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Clôturées (1)"));

    expect(screen.getByText("Facture erronée")).toBeInTheDocument();
    expect(screen.queryByText("Problème de connexion")).not.toBeInTheDocument();
    expect(screen.queryByText("Litige commande")).not.toBeInTheDocument();
  });

  it("shows a filter-specific empty state when no conversation matches the active status", async () => {
    mockFetch((url) =>
      url.startsWith("/api/sessions?user_id=") ? jsonResponse(sessions) : jsonResponse({}, 404)
    );

    renderDashboard();
    await screen.findByText("Problème de connexion");

    fireEvent.click(screen.getByText("Transférées (0)"));

    expect(await screen.findByText("Aucune conversation ne correspond à ce filtre.")).toBeInTheDocument();
  });
});
