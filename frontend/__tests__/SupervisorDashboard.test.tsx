import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import SupervisorDashboard from "@/components/dashboard/SupervisorDashboard";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

const usersByRole: Record<string, unknown[]> = {
  user: [{ id: 1, username: "alice", email: "alice@test.com", role: "user" }],
  sav: [{ id: 2, username: "bob", email: "bob@test.com", role: "sav" }],
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

describe("SupervisorDashboard", () => {
  it("loads and renders users and SAV agents in separate columns", async () => {
    mockFetch(handler);

    render(<SupervisorDashboard />, { wrapper: LocaleProvider });

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
  });

  it("embeds the SAV ticket queue below the team management panel", async () => {
    mockFetch(handler);

    render(<SupervisorDashboard />, { wrapper: LocaleProvider });

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(await screen.findByText("Aucun transfert")).toBeInTheDocument();
  });

  it("promotes a user to SAV and reloads the team", async () => {
    const fetchMock = mockFetch(handler);

    render(<SupervisorDashboard />, { wrapper: LocaleProvider });
    await screen.findByText("alice");

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

  it("demotes a SAV agent back to user", async () => {
    const fetchMock = mockFetch((url, init) => {
      if (/\/api\/users\/\d+\/role$/.test(url) && init?.method === "PUT") {
        return jsonResponse({ id: 2, username: "bob", email: "bob@test.com", role: "user" });
      }
      return handler(url, init);
    });

    render(<SupervisorDashboard />, { wrapper: LocaleProvider });
    await screen.findByText("bob");

    fireEvent.click(screen.getByRole("button", { name: /retirer/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/users/2/role",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ role: "user" }),
        })
      );
    });
  });

  it("shows a session-expired error when the users endpoint returns 401", async () => {
    mockFetch(() => jsonResponse({}, 401));

    render(<SupervisorDashboard />, { wrapper: LocaleProvider });

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
  });
});
