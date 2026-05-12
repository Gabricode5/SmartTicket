import { cn } from "../lib/utils";

describe("cn (className merger)", () => {
  it("returns a single class unchanged", () => {
    expect(cn("foo")).toBe("foo");
  });

  it("merges multiple classes", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("resolves tailwind conflicts — last value wins", () => {
    expect(cn("p-4", "p-8")).toBe("p-8");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
    expect(cn("font-bold", "font-normal")).toBe("font-normal");
  });

  it("ignores falsy values", () => {
    expect(cn("foo", false, undefined, null, "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    const isActive = true;
    const isDisabled = false;
    expect(cn("base", isActive && "active", isDisabled && "disabled")).toBe("base active");
  });

  it("handles object syntax", () => {
    expect(cn({ "font-bold": true, "text-gray-500": false })).toBe("font-bold");
  });

  it("returns empty string when all values are falsy", () => {
    expect(cn(false, undefined, null)).toBe("");
  });
});
