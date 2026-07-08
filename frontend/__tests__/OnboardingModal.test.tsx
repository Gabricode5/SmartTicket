import { render, screen, fireEvent } from "@testing-library/react";
import OnboardingModal, { onboardingStorageKey } from "@/components/onboarding/OnboardingModal";

beforeEach(() => {
  window.localStorage.clear();
});

describe("OnboardingModal", () => {
  it("shows the first step on first visit", () => {
    render(<OnboardingModal userId={1} role="user" />);
    expect(screen.getByText("Bienvenue sur SmartTicket")).toBeInTheDocument();
  });

  it("does not reopen once dismissed for this user/role", () => {
    window.localStorage.setItem(onboardingStorageKey(1, "user"), "1");
    render(<OnboardingModal userId={1} role="user" />);
    expect(screen.queryByText("Bienvenue sur SmartTicket")).not.toBeInTheDocument();
  });

  it("shows role-specific content", () => {
    render(<OnboardingModal userId={2} role="admin" />);
    expect(screen.getByText("Bienvenue, administrateur")).toBeInTheDocument();
  });

  it("falls back to the user steps for an unknown role", () => {
    render(<OnboardingModal userId={3} role="something_unexpected" />);
    expect(screen.getByText("Bienvenue sur SmartTicket")).toBeInTheDocument();
  });

  it("navigates forward and back through steps", () => {
    render(<OnboardingModal userId={1} role="user" />);
    fireEvent.click(screen.getByRole("button", { name: /suivant/i }));
    expect(screen.getByText("Démarrez une conversation")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /précédent/i }));
    expect(screen.getByText("Bienvenue sur SmartTicket")).toBeInTheDocument();
  });

  it("marks onboarding as seen and closes when skipped", () => {
    render(<OnboardingModal userId={1} role="user" />);
    fireEvent.click(screen.getByRole("button", { name: /passer/i }));

    expect(window.localStorage.getItem(onboardingStorageKey(1, "user"))).toBe("1");
    expect(screen.queryByText("Bienvenue sur SmartTicket")).not.toBeInTheDocument();
  });

  it("shows a Terminé button on the last step and marks onboarding as seen", () => {
    render(<OnboardingModal userId={1} role="user" />);
    // user role has 4 steps — click "Suivant" three times to reach the last one.
    fireEvent.click(screen.getByRole("button", { name: /suivant/i }));
    fireEvent.click(screen.getByRole("button", { name: /suivant/i }));
    fireEvent.click(screen.getByRole("button", { name: /suivant/i }));

    expect(screen.queryByRole("button", { name: /suivant/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /terminé/i }));

    expect(window.localStorage.getItem(onboardingStorageKey(1, "user"))).toBe("1");
  });
});
