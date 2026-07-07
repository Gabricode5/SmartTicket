import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import UserDashboard from "@/components/dashboard/UserDashboard";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

const push = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const sessions = [
  { id: 1, title: "Problème de connexion", date_creation: "2026-01-05T10:00:00Z", status: "open" },
  { id: 2, title: "Facture erronée", date_creation: "2026-01-01T10:00:00Z", status: "closed" },
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

    render(<UserDashboard userId={42} />);

    expect(await screen.findByText("Problème de connexion")).toBeInTheDocument();
    expect(screen.getByText("Facture erronée")).toBeInTheDocument();

    // 2 total, 1 closed -> 50% closure rate, 1 open
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("shows an empty state when the user has no sessions", async () => {
    mockFetch(() => jsonResponse([]));

    render(<UserDashboard userId={42} />);

    expect(await screen.findByText("Aucune conversation.")).toBeInTheDocument();
  });

  it("shows a session-expired error on 401", async () => {
    mockFetch(() => jsonResponse({}, 401));

    render(<UserDashboard userId={42} />);

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
  });

  it("filters the session list via the search box", async () => {
    mockFetch((url) =>
      url.startsWith("/api/sessions?user_id=") ? jsonResponse(sessions) : jsonResponse({}, 404)
    );

    render(<UserDashboard userId={42} />);
    await screen.findByText("Problème de connexion");

    fireEvent.change(screen.getByPlaceholderText("Rechercher des conversations..."), {
      target: { value: "facture" },
    });

    expect(screen.queryByText("Problème de connexion")).not.toBeInTheDocument();
    expect(screen.getByText("Facture erronée")).toBeInTheDocument();
  });

  it("closes an open session after confirmation and refreshes the list", async () => {
    const fetchMock = mockFetch((url) => {
      if (url.includes("/close")) return jsonResponse({});
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse(sessions);
      return jsonResponse({}, 404);
    });

    render(<UserDashboard userId={42} />);
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
});
