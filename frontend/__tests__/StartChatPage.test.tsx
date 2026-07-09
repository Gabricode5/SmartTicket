import { render, screen, waitFor } from "@testing-library/react";
import StartChatPage from "@/app/chat/page";
import { mockFetch, jsonResponse } from "../test-utils/fetchMock";

const replace = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

describe("StartChatPage", () => {
  beforeEach(() => {
    replace.mockClear();
  });

  it("creates a guest session and redirects to the chat", async () => {
    const fetchMock = mockFetch(() => jsonResponse({ session: { id: 42 } }));

    render(<StartChatPage />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/sessions/guest", { method: "POST" });
    });
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/ai-assistant/42"));
  });

  it("shows an error when the guest session cannot be created", async () => {
    mockFetch(() => jsonResponse({}, 500));

    render(<StartChatPage />);

    expect(await screen.findByText(/impossible de démarrer la conversation/i)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
