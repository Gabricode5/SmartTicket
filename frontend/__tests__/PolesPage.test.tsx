import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import PolesPage from "@/app/(dashboard)/poles/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}));

const adminMe = {
  id: 1, username: "admin", email: "admin@example.com", role: "admin",
  poles_enabled: true, pole_id: null, pole_nom: null, managed_poles: [],
};

const poles = [
  { id: 1, nom: "Général", is_global: true },
  { id: 2, nom: "Support", is_global: false },
];

function renderPage() {
  return render(<PolesPage />, { wrapper: LocaleProvider });
}

describe("PolesPage", () => {
  it("shows nothing sensitive and a short message when the feature flag is off", async () => {
    mockFetch((url) =>
      url === "/api/me" ? jsonResponse({ ...adminMe, poles_enabled: false }) : jsonResponse({}, 404)
    );
    renderPage();

    expect(await screen.findByText(/pas activé/i)).toBeInTheDocument();
    expect(screen.queryByText("Support")).not.toBeInTheDocument();
  });

  it("denies access with a short message for a non-admin even if the flag is on", async () => {
    mockFetch((url) =>
      url === "/api/me"
        ? jsonResponse({ ...adminMe, role: "sav", pole_id: 2, pole_nom: "Support" })
        : jsonResponse({}, 404)
    );
    renderPage();

    expect(await screen.findByText(/réservé au super admin/i)).toBeInTheDocument();
  });

  it("lists existing poles for the admin and marks the global one", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(adminMe);
      if (url === "/api/poles") return jsonResponse(poles);
      if (url === "/api/managers") return jsonResponse([]);
      if (url.startsWith("/api/users?role=superviseur")) return jsonResponse([]);
      return jsonResponse({}, 404);
    });
    renderPage();

    expect(await screen.findByText("Support")).toBeInTheDocument();
    expect(screen.getByText("Général")).toBeInTheDocument();
  });

  it("creates a new pole", async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url === "/api/me") return jsonResponse(adminMe);
      if (url === "/api/poles" && (!init || init.method === undefined)) return jsonResponse(poles);
      if (url === "/api/poles" && init?.method === "POST") return jsonResponse({ id: 3, nom: "Ventes", is_global: false }, 201);
      if (url === "/api/managers") return jsonResponse([]);
      if (url.startsWith("/api/users?role=superviseur")) return jsonResponse([]);
      return jsonResponse({}, 404);
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /nouveau pôle/i }));
    fireEvent.change(screen.getByLabelText(/nom du pôle/i), { target: { value: "Ventes" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/poles",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ nom: "Ventes" }) })
      );
    });
  });

  it("refuses to let the global pole be deleted (delete button disabled)", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(adminMe);
      if (url === "/api/poles") return jsonResponse(poles);
      if (url === "/api/managers") return jsonResponse([]);
      if (url.startsWith("/api/users?role=superviseur")) return jsonResponse([]);
      return jsonResponse({}, 404);
    });
    renderPage();
    await screen.findByText("Général");

    const generalCard = screen.getByText("Général").closest(".p-4") as HTMLElement;
    const deleteButtons = within(generalCard).getAllByRole("button");
    const trashButton = deleteButtons[deleteButtons.length - 1];
    expect(trashButton).toBeDisabled();
  });

  it("assigns a supervisor to selected poles as a manager", async () => {
    const superviseurs = [{ id: 5, username: "eve", email: "eve@example.com" }];
    const fetchMock = mockFetch((url, init) => {
      if (url === "/api/me") return jsonResponse(adminMe);
      if (url === "/api/poles") return jsonResponse(poles);
      if (url === "/api/managers") return jsonResponse([]);
      if (url.startsWith("/api/users?role=superviseur")) return jsonResponse(superviseurs);
      if (/\/api\/users\/5\/manager-poles$/.test(url) && init?.method === "PUT") return jsonResponse([poles[1]]);
      return jsonResponse({}, 404);
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /managers/i }));
    fireEvent.click(await screen.findByRole("combobox"));
    fireEvent.click(await screen.findByText(/eve \(eve@example.com\)/i));
    fireEvent.click(await screen.findByLabelText("Support"));
    fireEvent.click(screen.getByRole("button", { name: "Assigner" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/users/5/manager-poles",
        expect.objectContaining({ method: "PUT", body: JSON.stringify({ pole_ids: [2] }) })
      );
    });
  });
});
