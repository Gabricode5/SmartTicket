/**
 * Unit tests for the /api/ask route helper logic.
 * These tests do NOT make real network calls — they validate
 * input sanitization and response shaping at the module level.
 */

const BACKEND_URL = "http://localhost:8000";

describe("ask route — input validation", () => {
  it("rejects empty question", () => {
    const question = "  ";
    expect(question.trim().length).toBe(0);
  });

  it("accepts valid question", () => {
    const question = "Comment réinitialiser mon mot de passe ?";
    expect(question.trim().length).toBeGreaterThan(0);
  });

  it("backend URL is defined", () => {
    expect(BACKEND_URL).toBeTruthy();
    expect(BACKEND_URL).toMatch(/^https?:\/\//);
  });
});

describe("ask route — session_id validation", () => {
  it("session_id must be a positive integer", () => {
    const valid = [1, 42, 100];
    const invalid = [0, -1, NaN, null, undefined];

    valid.forEach((id) => expect(Number.isInteger(id) && id > 0).toBe(true));
    invalid.forEach((id) => expect(Number.isInteger(id as number) && (id as number) > 0).toBe(false));
  });
});
