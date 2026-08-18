import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import MonitoringPage from "@/app/(dashboard)/monitoring/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn(), push: jest.fn() }),
}));

// recharts a besoin de ResizeObserver (absent de jsdom) pour ResponsiveContainer -- hors
// sujet pour ces tests (section "trous de la base de connaissances", pas le graphique de
// latence), donc remplacé par un stub minimal plutôt que de polyfill ResizeObserver.
jest.mock("recharts", () => ({
  LineChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  ReferenceLine: () => null,
}));

const adminUser = { id: 1, username: "admin1", email: "admin1@example.com", role: "admin" };
const savUser = { id: 2, username: "agent2", email: "agent2@example.com", role: "sav" };

const emptyAiMetrics = {
  total_calls: 0, error_rate: 0, avg_latency_ms: null, avg_rag_chunks: 0, no_context_rate: 0,
  latency_trend: [], alerts: [], model_name: null, kb_events: [],
  prev_latency_ms: null, prev_error_rate: null, prev_no_context_rate: null,
  kb_score: null, negative_rate: 0,
};

const gapsData = {
  gaps: [
    { question: "Comment configurer mon compte ?", occurrences: 3, first_seen: "2026-01-01T10:00:00Z", last_seen: "2026-01-05T10:00:00Z", sample_session_id: 12 },
  ],
  total_gap_calls: 3,
  total_distinct_gaps: 1,
};

function mockCommonEndpoints(user: typeof adminUser, extra?: (url: string) => Response | undefined) {
  return mockFetch((url) => {
    const overridden = extra?.(url);
    if (overridden) return overridden;
    if (url === "/api/me") return jsonResponse(user);
    if (url === "/api/mistral-status") return jsonResponse({ overall: "operational", components: [], fetched_at: "2026-01-01T10:00:00Z" });
    if (url.startsWith("/api/analytics/ai-metrics")) return jsonResponse(emptyAiMetrics);
    return jsonResponse({}, 404);
  });
}

describe("MonitoringPage — section trous de la base de connaissances", () => {
  it("does not fetch or show the section for a sav user", async () => {
    const fetchMock = mockCommonEndpoints(savUser);

    render(<MonitoringPage />, { wrapper: LocaleProvider });

    await screen.findByText("Monitoring du modèle IA");
    expect(screen.queryByText("Trous de la base de connaissances")).not.toBeInTheDocument();
    const calledUrls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(calledUrls.some((u) => u.startsWith("/api/analytics/knowledge-gaps"))).toBe(false);
  });

  it("shows the empty state for an admin when there are no gaps", async () => {
    mockCommonEndpoints(adminUser, (url) =>
      url.startsWith("/api/analytics/knowledge-gaps")
        ? jsonResponse({ gaps: [], total_gap_calls: 0, total_distinct_gaps: 0 })
        : undefined
    );

    render(<MonitoringPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Trous de la base de connaissances")).toBeInTheDocument();
    expect(await screen.findByText(/Aucun trou détecté/)).toBeInTheDocument();
  });

  it("lists each gap with its question, occurrence count and last-seen date for an admin", async () => {
    mockCommonEndpoints(adminUser, (url) =>
      url.startsWith("/api/analytics/knowledge-gaps") ? jsonResponse(gapsData) : undefined
    );

    render(<MonitoringPage />, { wrapper: LocaleProvider });

    expect(await screen.findByText("Comment configurer mon compte ?")).toBeInTheDocument();
    expect(await screen.findByText("3 fois")).toBeInTheDocument();
    expect(await screen.findByText(/3 questions sans bonne réponse, 1 distincte/)).toBeInTheDocument();
  });

  it("re-fetches knowledge-gaps when the period changes", async () => {
    const fetchMock = mockCommonEndpoints(adminUser, (url) =>
      url.startsWith("/api/analytics/knowledge-gaps") ? jsonResponse(gapsData) : undefined
    );

    render(<MonitoringPage />, { wrapper: LocaleProvider });
    await screen.findByText("Comment configurer mon compte ?");

    fireEvent.click(screen.getByRole("button", { name: "90 Jours" }));

    await waitFor(() => {
      const calledUrls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(calledUrls.some((u) => u === "/api/analytics/knowledge-gaps?days=90")).toBe(true);
    });
  });
});
