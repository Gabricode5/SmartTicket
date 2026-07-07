import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";
import AdminDashboard from "@/components/dashboard/AdminDashboard";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

// AdminDashboard renders next/link, which expects an app-router context that
// isn't mounted under jsdom in these tests — swap it for a plain anchor.
jest.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

const usersByRole: Record<string, unknown[]> = {
  user: [{ id: 1, username: "alice", email: "alice@test.com", role: "user" }],
  sav: [{ id: 2, username: "bob", email: "bob@test.com", role: "sav" }],
  admin: [{ id: 3, username: "carol", email: "carol@test.com", role: "admin" }],
};

function handler(url: string, init?: RequestInit) {
  if (url.startsWith("/api/users?role=")) {
    const role = new URL(url, "http://localhost").searchParams.get("role") ?? "";
    return jsonResponse(usersByRole[role] ?? []);
  }
  if (url === "/api/sessions/transferred") return jsonResponse([]);
  if (/\/api\/users\/\d+\/role$/.test(url) && init?.method === "PUT") {
    return jsonResponse({ id: 1, username: "alice", email: "alice@test.com", role: "sav" });
  }
  return jsonResponse({}, 404);
}

describe("AdminDashboard", () => {
  it("loads and renders users grouped by role", async () => {
    mockFetch(handler);

    render(<AdminDashboard currentUserId={3} />);

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
    expect(screen.getByText("carol")).toBeInTheDocument();
  });

  it("shows a session-expired error when the users endpoint returns 401", async () => {
    mockFetch(() => jsonResponse({}, 401));

    render(<AdminDashboard currentUserId={3} />);

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
  });

  it("loads a user's sessions when selected", async () => {
    mockFetch((url, init) => {
      if (url.startsWith("/api/sessions?user_id=1")) {
        return jsonResponse([{ id: 7, title: "Souci de paiement", status: "open" }]);
      }
      return handler(url, init);
    });

    render(<AdminDashboard currentUserId={3} />);
    fireEvent.click(await screen.findByText("alice"));

    expect(await screen.findByText("Souci de paiement")).toBeInTheDocument();
  });

  it("promotes a user to SAV and reloads the lists", async () => {
    const fetchMock = mockFetch(handler);

    render(<AdminDashboard currentUserId={3} />);
    await screen.findByText("alice");

    // "SAV" (promote-to-SAV) is only rendered for rows in the "Utilisateurs"
    // column, and alice is the only user there — so the name is unambiguous.
    fireEvent.click(screen.getByRole("button", { name: /^sav$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/users/1/role",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ role: "sav" }),
        })
      );
    });
  });
});
