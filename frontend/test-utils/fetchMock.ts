/** Shared helpers for mocking `fetch` in component tests. Not itself a test
 * suite — kept outside `__tests__/` so Jest's default testMatch doesn't try
 * to run it. */

export function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

/**
 * Installs a `global.fetch` mock that dispatches on the request URL.
 * `handler` receives the URL (and init) of each call and returns a
 * `jsonResponse(...)`; unmatched URLs should return a 404 jsonResponse.
 */
export function mockFetch(
  handler: (url: string, init?: RequestInit) => Response
) {
  const fn = jest.fn((url: string, init?: RequestInit) =>
    Promise.resolve(handler(url, init))
  );
  global.fetch = fn as unknown as typeof fetch;
  return fn;
}
