import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TicketsListPage from "@/app/(dashboard)/tickets/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}));

const savUser = { id: 42, username: "agent42", email: "agent42@example.com", role: "sav" };
const regularUser = { id: 1, username: "client1", email: "client1@example.com", role: "user" };

const ticket = {
  id: 7, ticket_number: 1042, session_id: 3, status: "new", waiting_on: "us",
  assigned_agent_id: null, priority: "normal", reason: "technique", context_cutoff_message_id: 5,
  created_at: "2026-01-01T10:00:00Z", updated_at: "2026-01-01T10:05:00Z",
  client_username: "dave", client_email: "dave@example.com", assigned_agent_username: null,
};

describe("TicketsListPage", () => {
  it("shows an empty state when there are no tickets", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: 20 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Aucun ticket.")).toBeInTheDocument();
  });

  it("lists tickets with number, client, status, waiting_on and assignment", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [ticket], total: 1, page: 1, page_size: 20 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("#1042")).toBeInTheDocument();
    expect(screen.getByText("dave")).toBeInTheDocument();
    expect(screen.getByText("Nouveau")).toBeInTheDocument();
    expect(screen.getByText("À répondre")).toBeInTheDocument();
    expect(screen.getByText("Non assigné")).toBeInTheDocument();
  });

  it("shows 'Invité' instead of the raw guest username", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) {
        return jsonResponse({ items: [{ ...ticket, client_username: "guest_ab12cd", client_email: null }], total: 1, page: 1, page_size: 20 });
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
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: 20 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });
    await screen.findByText("Aucun ticket.");
    fireEvent.click(screen.getByRole("button", { name: /file/i }));

    await waitFor(() => {
      const calledUrls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(calledUrls.some((u) => u.startsWith("/api/tickets?") && u.includes("unassigned=true"))).toBe(true);
    });
  });

  it("applies assigned_agent_id=<me> when 'Mes tickets' is clicked", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: 20 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });
    await screen.findByText("Aucun ticket.");
    fireEvent.click(screen.getByRole("button", { name: /mes tickets/i }));

    await waitFor(() => {
      const calledUrls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(calledUrls.some((u) => u.includes("assigned_agent_id=42"))).toBe(true);
    });
  });

  it("searches via /api/tickets/search when a query is submitted", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(savUser);
      if (url.startsWith("/api/tickets/search")) return jsonResponse({ items: [ticket], total: 1, page: 1, page_size: 20 });
      if (url.startsWith("/api/tickets")) return jsonResponse({ items: [], total: 0, page: 1, page_size: 20 });
      return jsonResponse({}, 404);
    });

    render(<TicketsListPage />, { wrapper: LocaleProvider });
    await screen.findByText("Aucun ticket.");

    fireEvent.change(screen.getByPlaceholderText(/rechercher/i), { target: { value: "1042" } });
    fireEvent.submit(screen.getByPlaceholderText(/rechercher/i).closest("form")!);

    await waitFor(() => {
      const calledUrls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(calledUrls.some((u) => u.startsWith("/api/tickets/search?") && u.includes("q=1042"))).toBe(true);
    });
    expect(await screen.findByText("#1042")).toBeInTheDocument();
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
