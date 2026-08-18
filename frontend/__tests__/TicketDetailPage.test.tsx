import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TicketDetailPage from "@/app/(dashboard)/tickets/[id]/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

jest.mock("next/navigation", () => ({
  useParams: () => ({ id: "7" }),
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}));

// Requis par @radix-ui/react-select en jsdom (pas de vrai layout) — même fix que
// AiDisclosure.test.tsx pour le composant Select.
Element.prototype.scrollIntoView = jest.fn();

const savUser = { id: 42, username: "agent42", email: "agent42@example.com", role: "sav" };
const supervisorUser = { id: 99, username: "super99", email: "super99@example.com", role: "superviseur" };

const baseTicket = {
  id: 7, ticket_number: 1042, session_id: 3, status: "new", waiting_on: "us",
  assigned_agent_id: null, priority: "normal", reason: "technique", context_cutoff_message_id: 2,
  created_at: "2026-01-01T10:00:00Z", updated_at: "2026-01-01T10:05:00Z",
  client_username: "dave", client_email: "dave@example.com", assigned_agent_username: null,
};

const rawMessages = [
  { id: 1, type_envoyeur: "user", contenu: "Ma commande ne suit pas.", date_creation: "2026-01-01T09:58:00Z" },
  { id: 2, type_envoyeur: "ai", contenu: "Je n'ai pas trouvé votre commande.", date_creation: "2026-01-01T09:59:00Z" },
  { id: 3, type_envoyeur: "ai", contenu: "Vous avez été mis en relation avec un agent humain.", date_creation: "2026-01-01T10:00:00Z" },
];

function mockLoad(ticket = baseTicket, user = savUser) {
  return mockFetch((url) => {
    if (url === "/api/me") return jsonResponse(user);
    if (url === "/api/tickets/7") return jsonResponse(ticket);
    if (url.startsWith("/api/messages?session_id=3")) return jsonResponse(rawMessages);
    if (url.startsWith("/api/users?role=sav")) return jsonResponse([{ id: 55, username: "other_agent" }]);
    return jsonResponse({}, 404);
  });
}

describe("TicketDetailPage", () => {
  it("shows the AI context before transfer, excluding the post-cutoff system message", async () => {
    mockLoad();

    render(<TicketDetailPage />, { wrapper: LocaleProvider });

    await screen.findByText("Technique");
    // Le message id=2 apparaît deux fois (panneau contexte + conversation complète) — les
    // deux affichages sont attendus, on vérifie juste sa présence.
    expect(screen.getAllByText("Je n'ai pas trouvé votre commande.").length).toBeGreaterThan(0);
    // Message #3 (id > context_cutoff_message_id=2) est le message système de transfert —
    // ne doit PAS apparaître dans le panneau "Contexte IA avant transfert" (mais peut
    // apparaître dans la conversation complète, à côté).
    const contextPanelHeading = screen.getByText("Contexte IA avant transfert");
    const contextPanel = contextPanelHeading.closest(".bg-card")!;
    expect(contextPanel).not.toHaveTextContent("Vous avez été mis en relation");
  });

  it("shows the full conversation including messages after the cutoff", async () => {
    mockLoad();

    render(<TicketDetailPage />, { wrapper: LocaleProvider });

    await screen.findByText("Conversation complète");
    expect(await screen.findByText("Vous avez été mis en relation avec un agent humain.")).toBeInTheDocument();
  });

  it("lets a sav agent take an unassigned ticket", async () => {
    const fetchMock = mockLoad();
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/me") return Promise.resolve(jsonResponse(savUser));
      if (url === "/api/tickets/7" && !init) return Promise.resolve(jsonResponse(baseTicket));
      if (url === "/api/tickets/7/assign" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ ...baseTicket, assigned_agent_id: 42, assigned_agent_username: "agent42" }));
      }
      if (url.startsWith("/api/messages?session_id=3")) return Promise.resolve(jsonResponse(rawMessages));
      return Promise.resolve(jsonResponse({}, 404));
    });

    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    fireEvent.click(await screen.findByRole("button", { name: /prendre le ticket/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/tickets/7/assign", expect.objectContaining({ method: "POST" }));
    });
  });

  it("changes the status independently via the select", async () => {
    const fetchMock = mockLoad();
    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    await screen.findByText("Conversation complète");

    fetchMock.mockImplementationOnce((url: string, init?: RequestInit) => {
      if (url === "/api/tickets/7/status" && init?.method === "PATCH") {
        return Promise.resolve(jsonResponse({ ...baseTicket, status: "in_progress" }));
      }
      return Promise.resolve(jsonResponse({}, 404));
    });

    // Le select shadcn est un bouton (role=combobox), pas un <select> natif.
    fireEvent.click(screen.getAllByRole("combobox")[0]);
    fireEvent.click(await screen.findByText("En cours"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/tickets/7/status", expect.objectContaining({
        method: "PATCH", body: JSON.stringify({ status: "in_progress" }),
      }));
    });
  });

  it("toggles waiting_on independently of status", async () => {
    const fetchMock = mockLoad();
    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    await screen.findByText("Conversation complète");

    fireEvent.click(screen.getByRole("button", { name: "En attente client" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/tickets/7/waiting_on", expect.objectContaining({
        method: "PATCH", body: JSON.stringify({ waiting_on: "customer" }),
      }));
    });
  });

  it("sends a reply and reloads the ticket to reflect the waiting_on flip done server-side", async () => {
    const fetchMock = mockLoad();
    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    await screen.findByText("Conversation complète");

    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/messages" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: 4, contenu: "Voici la solution.", date_creation: "2026-01-01T10:10:00Z" }));
      }
      if (url === "/api/tickets/7") {
        return Promise.resolve(jsonResponse({ ...baseTicket, waiting_on: "customer" }));
      }
      return Promise.resolve(jsonResponse({}, 404));
    });

    const input = screen.getByPlaceholderText("Écrire une réponse au client...");
    fireEvent.change(input, { target: { value: "Voici la solution." } });
    fireEvent.click(screen.getByRole("button", { name: /envoyer/i }));

    expect(await screen.findByText("Voici la solution.")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/messages", expect.objectContaining({
        method: "POST", body: JSON.stringify({ id_session: 3, type_envoyeur: "sav", contenu: "Voici la solution." }),
      }));
    });
  });

  it("shows a visible error and keeps the draft when sending a reply fails", async () => {
    const fetchMock = mockLoad();
    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    await screen.findByText("Conversation complète");

    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/messages" && init?.method === "POST") return Promise.resolve(jsonResponse({}, 500));
      return Promise.resolve(jsonResponse({}, 404));
    });

    const input = screen.getByPlaceholderText("Écrire une réponse au client...");
    fireEvent.change(input, { target: { value: "Voici la solution." } });
    fireEvent.click(screen.getByRole("button", { name: /envoyer/i }));

    expect(await screen.findByText("Action impossible pour le moment.")).toBeInTheDocument();
    // Le texte n'est PAS perdu (le textarea le contient toujours) et le message n'a PAS été
    // ajouté à la conversation en plus -- une seule occurrence, celle du brouillon. L'agent
    // ne doit jamais croire qu'une réponse est partie alors que rien n'a été envoyé.
    expect(input).toHaveValue("Voici la solution.");
    expect(screen.getAllByText("Voici la solution.")).toHaveLength(1);
  });

  it("shows a multi-line textarea for the reply box, not a single-line input", async () => {
    mockLoad();
    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    await screen.findByText("Conversation complète");

    const textarea = screen.getByPlaceholderText("Écrire une réponse au client...");
    expect(textarea.tagName).toBe("TEXTAREA");
    expect(screen.getByText(/entrée pour envoyer/i)).toBeInTheDocument();
  });

  it("sends the reply on Enter without Shift", async () => {
    const fetchMock = mockLoad();
    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    await screen.findByText("Conversation complète");

    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/messages" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: 5, contenu: "Réponse rapide.", date_creation: "2026-01-01T10:10:00Z" }));
      }
      if (url === "/api/tickets/7") return Promise.resolve(jsonResponse(baseTicket));
      return Promise.resolve(jsonResponse({}, 404));
    });

    const textarea = screen.getByPlaceholderText("Écrire une réponse au client...");
    fireEvent.change(textarea, { target: { value: "Réponse rapide." } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/messages", expect.objectContaining({
        method: "POST", body: JSON.stringify({ id_session: 3, type_envoyeur: "sav", contenu: "Réponse rapide." }),
      }));
    });
  });

  it("does not send on Shift+Enter, so the agent can write a new line instead", async () => {
    const fetchMock = mockLoad();
    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    await screen.findByText("Conversation complète");

    const textarea = screen.getByPlaceholderText("Écrire une réponse au client...");
    fireEvent.change(textarea, { target: { value: "Première ligne" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });

    const postCalls = fetchMock.mock.calls.filter((c) => c[0] === "/api/messages");
    expect(postCalls.length).toBe(0);
  });

  it("lets a supervisor assign the ticket to a chosen agent", async () => {
    mockLoad(baseTicket, supervisorUser);
    render(<TicketDetailPage />, { wrapper: LocaleProvider });
    await screen.findByText("Conversation complète");

    // Le sélecteur d'agent est le dernier combobox (après le select de statut).
    const comboboxes = screen.getAllByRole("combobox");
    fireEvent.click(comboboxes[comboboxes.length - 1]);
    expect(await screen.findByText("other_agent")).toBeInTheDocument();
  });

  it("shows 'Ticket introuvable' on a 404", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url === "/api/tickets/7") return jsonResponse({}, 404);
      return jsonResponse({}, 404);
    });

    render(<TicketDetailPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Ticket introuvable.")).toBeInTheDocument();
  });
});
