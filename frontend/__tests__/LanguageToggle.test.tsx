import { render, screen, fireEvent } from "@testing-library/react";
import LandingPage from "@/app/page";
import { AppSidebar } from "@/components/app-sidebar";
import UserDashboard from "@/components/dashboard/UserDashboard";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

jest.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

const apiUser = { id: 1, username: "gabriel", email: "gabriel@example.com", role: "user" };

describe("Language switching", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders the landing page in French by default and switches to English", async () => {
    render(<LandingPage />, { wrapper: LocaleProvider });

    expect((await screen.findAllByText("Comment ça marche")).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "English" })).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "English" })[0]);

    expect((await screen.findAllByText("How it works")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Comment ça marche")).not.toBeInTheDocument();
  });

  it("persists the chosen locale in localStorage", async () => {
    render(<LandingPage />, { wrapper: LocaleProvider });
    fireEvent.click(screen.getAllByRole("button", { name: "English" })[0]);

    await screen.findAllByText("How it works");
    expect(localStorage.getItem("locale")).toBe("en");
  });

  it("switching the language from the sidebar also translates the dashboard", async () => {
    mockFetch((url) => {
      if (url === "/api/me") return jsonResponse(apiUser);
      if (url.startsWith("/api/sessions?user_id=")) return jsonResponse([]);
      return jsonResponse({}, 404);
    });

    render(
      <LocaleProvider>
        <AppSidebar />
        <UserDashboard userId={1} />
      </LocaleProvider>
    );

    expect((await screen.findAllByText("Tableau de bord")).length).toBeGreaterThan(0);
    expect(screen.getByText("Discussions")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "English" })[0]);

    expect((await screen.findAllByText("Dashboard")).length).toBeGreaterThan(0);
    expect(screen.getByText("Discussions")).toBeInTheDocument(); // same word in both languages
    expect(screen.queryByText("Tableau de bord")).not.toBeInTheDocument();
  });
});
