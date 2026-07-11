import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import SavDashboard from "@/components/dashboard/SavDashboard";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

const transferredSessions = [
  {
    id: 5,
    title: "Bug application",
    status: "transferred",
    transfer_reason: "technique",
    date_creation: "2026-01-01T10:00:00Z",
    username: "dave",
  },
];

const messages = [
  { id: 10, type_envoyeur: "user", contenu: "Bonjour, j'ai un souci.", date_creation: "2026-01-01T10:01:00Z" },
];

describe("SavDashboard", () => {
  it("shows an empty queue when there are no transferred sessions", async () => {
    mockFetch(() => jsonResponse([]));

    render(<SavDashboard />);

    expect(await screen.findByText("Aucun transfert")).toBeInTheDocument();
  });

  it("loads the transferred sessions queue", async () => {
    mockFetch((url) =>
      url === "/api/sessions/transferred" ? jsonResponse(transferredSessions) : jsonResponse({}, 404)
    );

    render(<SavDashboard />);

    expect(await screen.findByText("dave")).toBeInTheDocument();
    expect(screen.getByText("Bug application")).toBeInTheDocument();
    expect(screen.getByText("Technique")).toBeInTheDocument();
  });

  it("groups the queue by date period", async () => {
    const today = new Date().toISOString();
    const sessionsAcrossPeriods = [
      { ...transferredSessions[0], id: 6, username: "alice", date_creation: today },
      { ...transferredSessions[0], id: 7, username: "bob", date_creation: "2026-01-01T10:00:00Z" },
    ];
    mockFetch((url) =>
      url === "/api/sessions/transferred" ? jsonResponse(sessionsAcrossPeriods) : jsonResponse({}, 404)
    );

    render(<SavDashboard />);

    expect(await screen.findByText("Aujourd'hui")).toBeInTheDocument();
    expect(screen.getByText("Janvier 2026")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
  });

  it("loads the conversation when a queued session is selected", async () => {
    mockFetch((url) => {
      if (url === "/api/sessions/transferred") return jsonResponse(transferredSessions);
      if (url.startsWith("/api/messages?session_id=5")) return jsonResponse(messages);
      return jsonResponse({}, 404);
    });

    render(<SavDashboard />);
    fireEvent.click(await screen.findByText("dave"));

    expect(await screen.findByText("Bonjour, j'ai un souci.")).toBeInTheDocument();
  });

  it("sends a reply and appends it to the conversation", async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url === "/api/sessions/transferred") return jsonResponse(transferredSessions);
      if (url.startsWith("/api/messages?session_id=5")) return jsonResponse(messages);
      if (url === "/api/messages" && init?.method === "POST") {
        return jsonResponse({ id: 11, contenu: "Voici la solution.", date_creation: "2026-01-01T10:05:00Z" });
      }
      return jsonResponse({}, 404);
    });

    render(<SavDashboard />);
    fireEvent.click(await screen.findByText("dave"));
    await screen.findByText("Bonjour, j'ai un souci.");

    const input = screen.getByPlaceholderText("Écrire une réponse au client...");
    fireEvent.change(input, { target: { value: "Voici la solution." } });
    fireEvent.click(screen.getByRole("button", { name: /envoyer/i }));

    expect(await screen.findByText("Voici la solution.")).toBeInTheDocument();
    expect(input).toHaveValue("");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/messages",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ id_session: 5, type_envoyeur: "sav", contenu: "Voici la solution." }),
      })
    );
  });

  it("resolves the session and returns it to the AI", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/sessions/transferred") return jsonResponse(transferredSessions);
      if (url.startsWith("/api/messages?session_id=5")) return jsonResponse(messages);
      if (url === "/api/sessions/5/resolve") return jsonResponse({});
      return jsonResponse({}, 404);
    });

    render(<SavDashboard />);
    fireEvent.click(await screen.findByText("dave"));
    await screen.findByText("Bonjour, j'ai un souci.");

    fireEvent.click(screen.getByRole("button", { name: /remettre à l'ia/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/sessions/5/resolve", { method: "POST" });
    });
    expect(await screen.findByText("Aucun transfert")).toBeInTheDocument();
  });
});
