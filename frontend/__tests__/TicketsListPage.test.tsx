import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TicketsListPage from "@/app/(dashboard)/tickets/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}));

// Requis par @radix-ui/react-select en jsdom (pas de vrai layout) — même fix que
// AiDisclosure.test.tsx / TicketDetailPage.test.tsx pour le composant Select.
Element.prototype.scrollIntoView = jest.fn();

const savUser = { id: 42, username: "agent42", email: "agent42@example.com", role: "sav" };
const regularUser = { id: 1, username: "client1", email: "client1@example.com", role: "user" };

// waiting_on="us" + status="new" -> tombe dans la section "À répondre" (cf. bucketTickets).
const needsReplyTicket = {
  id: 7, ticket_number: 1042, session_id: 3, status: "new", waiting_on: "us",
  assigned_agent_id: null, priority: "normal", reason: "technique", context_cutoff_message_id: 5,
  created_at: "2026-01-01T10:00:00Z", updated_at: "2026-01-01T10:05:00Z",
  client_username: "dave", client_email: "dave@example.com", assigned_agent_username: null,
};

describe("TicketsListPage — vue groupée par défaut", () => {
  it("shows the per-section empty states when there are no tickets", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: 100 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Rien à traiter, bravo !")).toBeInTheDocument();
    expect(screen.getByText("Aucun ticket en attente du client.")).toBeInTheDocument();
    expect(screen.getByText("À répondre (0)")).toBeInTheDocument();
    expect(screen.getByText("En attente client (0)")).toBeInTheDocument();
    expect(screen.getByText("Résolus / Fermés (0)")).toBeInTheDocument();
  });

  it("lists a needs-reply ticket under 'À répondre' with the number, client, status and assignment", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [needsReplyTicket], total: 1, page: 1, page_size: 100 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("À répondre (1)")).toBeInTheDocument();
    expect(screen.getByText("#1042")).toBeInTheDocument();
    expect(screen.getByText("dave")).toBeInTheDocument();
    expect(screen.getByText("Nouveau")).toBeInTheDocument();
    expect(screen.getByText("Non assigné")).toBeInTheDocument();
  });

  it("buckets a resolved ticket into 'Résolus / Fermés' even though waiting_on is still 'us'", async () => {
    // Précédence status sur waiting_on : un ticket clôturé sort du flux de travail actif
    // quel que soit son waiting_on (cf. commentaire bucketTickets).
    const resolvedTicket = { ...needsReplyTicket, id: 8, ticket_number: 1043, status: "resolved" };
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [resolvedTicket], total: 1, page: 1, page_size: 100 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("À répondre (0)")).toBeInTheDocument();
    expect(screen.getByText("En attente client (0)")).toBeInTheDocument();
    expect(screen.getByText("Résolus / Fermés (1)")).toBeInTheDocument();
    // Section repliée par défaut : la ligne n'est pas encore dans le DOM.
    expect(screen.queryByText("#1043")).not.toBeInTheDocument();
  });

  it("expands the collapsed 'Résolus / Fermés' section on click", async () => {
    const resolvedTicket = { ...needsReplyTicket, id: 8, ticket_number: 1043, status: "closed" };
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [resolvedTicket], total: 1, page: 1, page_size: 100 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });
    fireEvent.click(await screen.findByText("Résolus / Fermés (1)"));

    expect(await screen.findByText("#1043")).toBeInTheDocument();
  });

  it("shows 'Invité' instead of the raw guest username", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) {
        return jsonResponse({ items: [{ ...needsReplyTicket, client_username: "guest_ab12cd", client_email: null }], total: 1, page: 1, page_size: 100 });
      }
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Invité")).toBeInTheDocument();
    expect(screen.queryByText("guest_ab12cd")).not.toBeInTheDocument();
  });

  it("redirects a regular user away (no ticket UI ever rendered)", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(regularUser);
      return jsonResponse({}, 404);
    });

    const { container } = render(<TicketsListPage />, { wrapper: LocaleProvider });

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("applies unassigned=true when the 'File' quick filter is clicked", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: 100 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });
    await screen.findByText("Rien à traiter, bravo !");
    fireEvent.click(screen.getByRole("button", { name: /file/i }));

    await waitFor(() => {
      const calledUrls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(calledUrls.some((u) => u.startsWith("/api/tickets?") && u.includes("unassigned=true"))).toBe(true);
    });
  });

  it("applies assigned_agent_id=<me> when 'Mes tickets' is clicked", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: 100 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });
    await screen.findByText("Rien à traiter, bravo !");
    fireEvent.click(screen.getByRole("button", { name: /mes tickets/i }));

    await waitFor(() => {
      const calledUrls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(calledUrls.some((u) => u.includes("assigned_agent_id=42"))).toBe(true);
    });
  });

  it("shows a subscription-suspended banner on a 402 response", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ detail: "Suspendu" }, 402);
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText(/service est suspendu/i)).toBeInTheDocument();
  });
});

describe("TicketsListPage — filtre explicite ou recherche : retour à la liste plate paginée", () => {
  it("searches via /api/tickets/search when a query is submitted", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets/search")) return jsonResponse({ items: [needsReplyTicket], total: 1, page: 1, page_size: 20 });
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: 100 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });
    await screen.findByText("Rien à traiter, bravo !");

    fireEvent.change(screen.getByPlaceholderText(/rechercher/i), { target: { value: "1042" } });
    fireEvent.submit(screen.getByPlaceholderText(/rechercher/i).closest("form")!);

    await waitFor(() => {
      const calledUrls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(calledUrls.some((u) => u.startsWith("/api/tickets/search?") && u.includes("q=1042"))).toBe(true);
    });
    expect(await screen.findByText("#1042")).toBeInTheDocument();
    // Vue plate, pas de sections groupées pendant une recherche.
    expect(screen.queryByText("À répondre (1)")).not.toBeInTheDocument();
  });

  it("shows the flat empty state ('Aucun ticket.') once a status filter is applied", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: url.includes("status=") ? 20 : 100 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });
    await screen.findByText("Rien à traiter, bravo !");

    fireEvent.click(screen.getAllByRole("combobox")[0]);
    fireEvent.click(await screen.findByText("En cours"));

    expect(await screen.findByText("Aucun ticket.")).toBeInTheDocument();
  });
});
