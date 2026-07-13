import { render, screen, fireEvent } from "@testing-library/react";
import LandingPage from "@/app/page";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";

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
});
