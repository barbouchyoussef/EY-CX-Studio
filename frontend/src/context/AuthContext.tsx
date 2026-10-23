import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  apiAcceptInvite,
  apiGetMe,
  apiLogin,
  apiLogout,
  apiResetPassword,
  refreshAccessToken,
  setLogoutHandler,
  type AuthUser,
} from "../lib/api";

interface AuthState {
  user: AuthUser | null;
  loading: boolean; // true only during the initial session-restore
  login: (email: string, password: string) => Promise<void>;
  acceptInvite: (token: string, fullName: string, password: string) => Promise<void>;
  resetPassword: (token: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Replace the cached user after a self-service profile edit, so the header updates at once. */
  applyUser: (u: AuthUser) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Let authFetch drop us to a logged-out state if a silent refresh ever fails mid-session.
  useEffect(() => {
    setLogoutHandler(() => setUser(null));
    return () => setLogoutHandler(null);
  }, []);

  // On first load, try to restore a session from the HttpOnly refresh cookie.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await refreshAccessToken();
      if (token) {
        try {
          const me = await apiGetMe();
          if (!cancelled) setUser(me);
        } catch {
          /* refresh worked but /me failed -- stay logged out */
        }
      }
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (email: string, password: string) => {
    setUser(await apiLogin(email, password));
  };
  const acceptInvite = async (token: string, fullName: string, password: string) => {
    setUser(await apiAcceptInvite(token, fullName, password));
  };
  const resetPassword = async (token: string, password: string) => {
    setUser(await apiResetPassword(token, password));
  };
  const logout = async () => {
    await apiLogout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, acceptInvite, resetPassword, logout, applyUser: setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
