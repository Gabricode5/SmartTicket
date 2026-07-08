import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NotificationBell } from "@/components/NotificationBell";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

const push = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const notifications = [
  { id: 1, type: "sav_reply", message: "Un agent SAV a répondu à votre ticket « Souci » .", id_session: 42, read: false, date_creation: "2026-01-05T10:00:00Z" },
  { id: 2, type: "session_transferred", message: "Nouveau ticket transféré.", id_session: 7, read: true, date_creation: "2026-01-04T10:00:00Z" },
];

describe("NotificationBell", () => {
  beforeEach(() => {
    push.mockClear();
  });

  it("shows the unread count badge on mount", async () => {
    mockFetch((url) => {
      if (url === "/api/notifications/unread-count") return jsonResponse({ count: 3 });
      return jsonResponse({});
    });

    render(<NotificationBell />);

    expect(await screen.findByText("3")).toBeInTheDocument();
  });

  it("hides the badge when there are no unread notifications", async () => {
    mockFetch(() => jsonResponse({ count: 0 }));

    render(<NotificationBell />);

    await waitFor(() => expect(screen.getByLabelText("Notifications")).toBeInTheDocument());
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("opens the dropdown and lists notifications", async () => {
    mockFetch((url) => {
      if (url === "/api/notifications/unread-count") return jsonResponse({ count: 1 });
      if (url === "/api/notifications") return jsonResponse(notifications);
      return jsonResponse({});
    });

    render(<NotificationBell />);
    fireEvent.click(await screen.findByLabelText("Notifications"));

    expect(await screen.findByText(/un agent sav a répondu/i)).toBeInTheDocument();
    expect(screen.getByText(/nouveau ticket transféré/i)).toBeInTheDocument();
  });

  it("marks a notification as read and navigates to its session when clicked", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/notifications/unread-count") return jsonResponse({ count: 1 });
      if (url === "/api/notifications") return jsonResponse(notifications);
      if (url === "/api/notifications/1/read") return jsonResponse({ ...notifications[0], read: true });
      return jsonResponse({});
    });

    render(<NotificationBell />);
    fireEvent.click(await screen.findByLabelText("Notifications"));
    fireEvent.click(await screen.findByText(/un agent sav a répondu/i));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/notifications/1/read", expect.objectContaining({ method: "PATCH" }));
    });
    expect(push).toHaveBeenCalledWith("/ai-assistant/42");
  });

  it("marks all notifications as read", async () => {
    const fetchMock = mockFetch((url) => {
      if (url === "/api/notifications/unread-count") return jsonResponse({ count: 1 });
      if (url === "/api/notifications") return jsonResponse(notifications);
      if (url === "/api/notifications/read-all") return jsonResponse({ ok: true });
      return jsonResponse({});
    });

    render(<NotificationBell />);
    fireEvent.click(await screen.findByLabelText("Notifications"));
    fireEvent.click(await screen.findByText(/tout marquer lu/i));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/notifications/read-all", expect.objectContaining({ method: "POST" }));
    });
  });
});
