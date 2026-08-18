import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import type { ReactNode } from "react";
import AdminDashboard from "@/components/dashboard/AdminDashboard";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

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
  superviseur: [{ id: 4, username: "dave", email: "dave@test.com", role: "superviseur" }],
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

    render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });

    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
    expect(screen.getByText("carol")).toBeInTheDocument();
    // Regression test: a "superviseur" account must be visible in its own
    // column, not silently dropped because loadAll() only used to fetch
    // role=user/sav/admin.
    expect(screen.getByText("dave")).toBeInTheDocument();
  });

  it("shows a session-expired error when the users endpoint returns 401", async () => {
    mockFetch(() => jsonResponse({}, 401));

    render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
  });

  it("loads a user's sessions when selected", async () => {
    mockFetch((url, init) => {
      if (url.startsWith("/api/sessions?user_id=1")) {
        return jsonResponse([{ id: 7, title: "Souci de paiement", status: "open" }]);
      }
      return handler(url, init);
    });

    render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });
    fireEvent.click(await screen.findByText("alice"));

    expect(await screen.findByText("Souci de paiement")).toBeInTheDocument();
  });

  it("searches the selected user's conversations and highlights the match", async () => {
    const sessions = [{ id: 7, title: "Souci de paiement", status: "open" }];
    const searchResults = [
      { id: 7, title: "Souci de paiement", status: "open", snippet: "problème de <b>paiement</b> récurrent" },
    ];
    const fetchMock = mockFetch((url, init) => {
      if (url.startsWith("/api/sessions/search")) return jsonResponse(searchResults);
      if (url.startsWith("/api/sessions?user_id=1")) return jsonResponse(sessions);
      return handler(url, init);
    });

    render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });
    fireEvent.click(await screen.findByText("alice"));
    await screen.findByText("Souci de paiement");

    fireEvent.change(screen.getByPlaceholderText("Rechercher dans les conversations..."), {
      target: { value: "paiement" },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/sessions/search?user_id=1&q=paiement");
    });

    expect(await screen.findByText("paiement", { selector: "strong" })).toBeInTheDocument();
  });

  it("clears the previous search when a different user is selected", async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url.startsWith("/api/sessions/search")) return jsonResponse([{ id: 7, title: "X", status: "open", snippet: "<b>x</b>" }]);
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse([]);
      return handler(url, init);
    });

    render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });
    fireEvent.click(await screen.findByText("alice"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions?user_id=1"));

    fireEvent.change(screen.getByPlaceholderText("Rechercher dans les conversations..."), {
      target: { value: "paiement" },
    });
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/sessions/search?user_id=1&q=paiement");
    });

    fireEvent.click(screen.getByText("bob"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions?user_id=2"));

    expect(screen.getByPlaceholderText("Rechercher dans les conversations...")).toHaveValue("");
  });

  it("promotes a user to SAV and reloads the lists", async () => {
    const fetchMock = mockFetch(handler);

    render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });
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

  // RGPD (2026-08-19) : un utilisateur final (rôle "user") est seul propriétaire de son
  // identité -- le formulaire d'édition ne doit ni pré-remplir des champs modifiables pour
  // lui, ni les envoyer au backend qui les refuserait de toute façon (défense en profondeur,
  // la vraie protection est côté backend).
  describe("edit dialog — protection RGPD des données personnelles d'un utilisateur final", () => {
    function getUserRow(usernameText: string) {
      const usernameNode = screen.getByText(usernameText);
      return usernameNode.closest("button")!.parentElement as HTMLElement;
    }

    it("disables identity fields and shows an explanatory note for an end user (role=user)", async () => {
      mockFetch(handler);
      render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });
      await screen.findByText("alice");

      const editButton = within(getUserRow("alice")).getAllByRole("button")[2];
      fireEvent.click(editButton);

      expect(await screen.findByText("Modifier l'utilisateur")).toBeInTheDocument();
      expect(screen.getByText(/appartiennent au client/i)).toBeInTheDocument();
      expect(screen.getByLabelText("Prénom")).toBeDisabled();
      expect(screen.getByLabelText("Nom")).toBeDisabled();
      expect(screen.getByLabelText("Nom d'utilisateur")).toBeDisabled();
      expect(screen.getByLabelText("Email")).toBeDisabled();
    });

    it("only sends the role when saving an end user's edit, never identity fields", async () => {
      const fetchMock = mockFetch((url, init) => {
        if (url === "/api/users/1" && init?.method === "PUT") {
          return jsonResponse({ id: 1, username: "alice", email: "alice@test.com", role: "sav" });
        }
        return handler(url, init);
      });
      render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });
      await screen.findByText("alice");

      fireEvent.click(within(getUserRow("alice")).getAllByRole("button")[2]);
      await screen.findByText("Modifier l'utilisateur");
      fireEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          "/api/users/1",
          expect.objectContaining({ method: "PUT", body: JSON.stringify({ role: "user" }) })
        );
      });
    });

    it("keeps identity fields editable for a team member (sav/superviseur/admin)", async () => {
      mockFetch(handler);
      render(<AdminDashboard currentUserId={3} />, { wrapper: LocaleProvider });
      await screen.findByText("bob"); // bob = role sav

      const editButton = within(getUserRow("bob")).getAllByRole("button")[2];
      fireEvent.click(editButton);

      await screen.findByText("Modifier l'utilisateur");
      expect(screen.queryByText(/appartiennent au client/i)).not.toBeInTheDocument();
      expect(screen.getByLabelText("Nom d'utilisateur")).not.toBeDisabled();
      expect(screen.getByLabelText("Email")).not.toBeDisabled();
    });
  });
});
