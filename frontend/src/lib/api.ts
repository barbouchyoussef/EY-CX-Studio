// Auth-aware API client.
//
// The access token is held in a module-level variable -- IN MEMORY ONLY. It is never written
// to localStorage/sessionStorage, so a cross-site-scripting bug cannot read a durable session.
// The long-lived credential is the refresh token, which lives in an HttpOnly cookie the JS
// here can neither read nor write; we only ride it via `credentials: "include"`.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

let accessToken: string | null = null;
let onLogout: (() => void) | null = null;

/** AuthContext registers a handler so a failed silent-refresh can clear React state. */
export function setLogoutHandler(handler: (() => void) | null): void {
  onLogout = handler;
}

async function parseError(res: Response, fallback: string): Promise<never> {
  let detail = fallback;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    /* non-JSON error body -- keep the fallback */
  }
  throw new Error(detail);
}

// A single shared in-flight refresh. Refresh tokens rotate on every use with server-side
// reuse detection, so two concurrent /auth/refresh calls (StrictMode double-mount, or several
// 401s at once) would replay the same cookie and trip that detection -- logging the user out.
// Collapsing concurrent callers onto one request guarantees exactly one rotation.
let refreshInFlight: Promise<string | null> | null = null;

/** Exchange the refresh cookie for a fresh access token. Returns it, or null on failure. */
export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return null;
      const data = await res.json();
      accessToken = data.access_token;
      return accessToken;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

/**
 * fetch() against the API with the bearer token attached and the refresh cookie included.
 * On 401 it tries a single silent refresh + retry before giving up and signalling logout.
 * `path` is relative to the API base, e.g. "/auth/me".
 */
/** Like authFetch but takes a fully-qualified URL (for call sites that already build
 *  `${API_BASE_URL}/...`). Same token + refresh-on-401 behaviour. */
export async function authFetchUrl(
  url: string,
  init: RequestInit = {},
  retryOn401 = true,
): Promise<Response> {
  const headers = new Headers(init.headers ?? {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const res = await fetch(url, { ...init, headers, credentials: "include" });

  if (res.status === 401 && retryOn401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return authFetchUrl(url, init, false); // retry once with the new token
    accessToken = null;
    onLogout?.();
  }
  return res;
}

/** fetch() against the API with the bearer token attached. `path` is relative to the API base. */
export async function authFetch(
  path: string,
  init: RequestInit = {},
  retryOn401 = true,
): Promise<Response> {
  return authFetchUrl(`${API_BASE_URL}${path}`, init, retryOn401);
}

// --------------------------------------------------------------------------- //
// Auth endpoints                                                                //
// --------------------------------------------------------------------------- //

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "consultant";
  status: string;
  created_at: string;
}

export async function apiLogin(email: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) await parseError(res, "Invalid credentials");
  const data = await res.json();
  accessToken = data.access_token;
  return data.user;
}

export async function apiAcceptInvite(
  token: string,
  fullName: string,
  password: string,
): Promise<AuthUser> {
  const res = await fetch(`${API_BASE_URL}/auth/accept`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, full_name: fullName, password }),
  });
  if (!res.ok) await parseError(res, "Could not accept invitation");
  const data = await res.json();
  accessToken = data.access_token;
  return data.user;
}

export async function apiGetMe(): Promise<AuthUser> {
  const res = await authFetch("/auth/me");
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

export async function apiLogout(): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST", credentials: "include" });
  accessToken = null;
}

/** Always resolves: the server returns 202 whether or not the email exists (no enumeration). */
export async function apiForgotPassword(email: string): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/forgot-password`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function apiResetPassword(token: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_BASE_URL}/auth/reset-password`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
  if (!res.ok) await parseError(res, "Could not reset password");
  const data = await res.json();
  accessToken = data.access_token; // reset auto-logs-in
  return data.user;
}

export async function apiChangePassword(current: string, next: string): Promise<void> {
  const res = await authFetch("/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: current, new_password: next }),
  });
  if (!res.ok) await parseError(res, "Could not change password");
  const data = await res.json();
  accessToken = data.access_token; // current session stays valid via the re-issued token
}

/** Update the signed-in user's own display name. Returns the refreshed user. */
export async function apiUpdateProfile(fullName: string): Promise<AuthUser> {
  const res = await authFetch("/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: fullName }),
  });
  if (!res.ok) await parseError(res, "Could not update your profile");
  return res.json();
}

// -------- Admin: user management + invites --------

export async function adminListUsers(): Promise<AuthUser[]> {
  const res = await authFetch("/auth/users");
  if (!res.ok) throw new Error("Failed to load users");
  return res.json();
}

export async function adminUpdateUser(
  id: number,
  patch: { role?: "admin" | "consultant"; status?: "active" | "disabled" },
): Promise<AuthUser> {
  const res = await authFetch(`/auth/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) await parseError(res, "Failed to update user");
  return res.json();
}

export interface InviteResult {
  email: string;
  role: string;
  token: string;
  accept_path: string;
}

export async function apiInvite(
  email: string,
  role: "admin" | "consultant",
): Promise<InviteResult> {
  const res = await authFetch("/auth/invite", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
  });
  if (!res.ok) await parseError(res, "Failed to create invitation");
  return res.json();
}
