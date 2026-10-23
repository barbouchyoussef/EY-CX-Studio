/**
 * The auth client's two load-bearing behaviours: never persisting the access token, and
 * recovering from a 401 exactly once.
 *
 * Both are security properties rather than features. The token is deliberately held in a module
 * variable so an XSS bug cannot read a durable session, and the refresh is deliberately collapsed
 * onto one in-flight request because refresh tokens rotate with server-side reuse detection --
 * two concurrent refreshes replay the same cookie and log the user out.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { authFetch, refreshAccessToken, setLogoutHandler } from "./api";

const ok = (body: unknown = {}) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const unauthorized = () => new Response("", { status: 401 });

describe("authFetch", () => {
  beforeEach(() => {
    setLogoutHandler(null);
    vi.unstubAllGlobals();
  });

  it("sends the refresh cookie with every request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok());
    vi.stubGlobal("fetch", fetchMock);

    await authFetch("/auth/me");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
  });

  it("refreshes once and retries when a request comes back 401", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(unauthorized())               // the original request
      .mockResolvedValueOnce(ok({ access_token: "fresh" })) // /auth/refresh
      .mockResolvedValueOnce(ok({ id: 1 }));                // the retry
    vi.stubGlobal("fetch", fetchMock);

    const res = await authFetch("/auth/me");

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[1][0])).toContain("/auth/refresh");
    // The retry must carry the new token, not the stale one.
    const retryHeaders = fetchMock.mock.calls[2][1].headers as Headers;
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh");
  });

  it("does not retry a second time when the refresh itself fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(unauthorized())  // original
      .mockResolvedValueOnce(unauthorized()); // refresh also refused
    vi.stubGlobal("fetch", fetchMock);
    const logout = vi.fn();
    setLogoutHandler(logout);

    const res = await authFetch("/auth/me");

    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2); // no third attempt
    expect(logout).toHaveBeenCalledOnce();
  });

  it("never writes the access token to browser storage", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok({ access_token: "secret-token" }));
    vi.stubGlobal("fetch", fetchMock);

    await refreshAccessToken();

    const stored = [
      ...Object.values(localStorage),
      ...Object.values(sessionStorage),
      localStorage.getItem("access_token"),
      sessionStorage.getItem("access_token"),
    ].join(" ");
    expect(stored).not.toContain("secret-token");
  });

  it("collapses concurrent refreshes onto a single request", async () => {
    // Two rotations of one refresh cookie trip the server's reuse detection, which revokes the
    // whole family. Concurrent callers must share one in-flight request.
    const fetchMock = vi.fn().mockResolvedValue(ok({ access_token: "fresh" }));
    vi.stubGlobal("fetch", fetchMock);

    await Promise.all([refreshAccessToken(), refreshAccessToken(), refreshAccessToken()]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
