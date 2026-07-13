import { render, screen, fireEvent } from "@testing-library/react";
import { AppSidebar } from "@/components/app-sidebar";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

function renderSidebar() {
  return render(<AppSidebar />, { wrapper: LocaleProvider });
}

jest.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}));

const apiUser = { id: 1, username: "gabriel", email: "gabriel@example.com", role: "user" };

const conversations = [
  { id: 1, title: "Question du jour", date_creation: new Date().toISOString() },
  { id: 2, title: "Vieille question", date_creation: "2026-01-01T10:00:00Z" },
];

function setupFetch() {
  return mockFetch((url) => {
    if (url === "/api/me") return jsonResponse(apiUser);
    if (url.startsWith("/api/sessions?user_id=")) return jsonResponse(conversations);
    return jsonResponse({}, 404);
  });
}

describe("AppSidebar", () => {
  it("groups the conversation history by date period", async () => {
    setupFetch();

    renderSidebar();

    expect(await screen.findByText("Question du jour")).toBeInTheDocument();
    expect(screen.getByText("Aujourd'hui")).toBeInTheDocument();
    expect(screen.getByText("Janvier 2026")).toBeInTheDocument();
    expect(screen.getByText("Vieille question")).toBeInTheDocument();
  });

  it("collapses and expands a group when its header is clicked", async () => {
    setupFetch();

    renderSidebar();
    await screen.findByText("Vieille question");

    fireEvent.click(screen.getByText("Janvier 2026"));
    expect(screen.queryByText("Vieille question")).not.toBeInTheDocument();
    // The other group stays untouched.
    expect(screen.getByText("Question du jour")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Janvier 2026"));
    expect(await screen.findByText("Vieille question")).toBeInTheDocument();
  });
});
