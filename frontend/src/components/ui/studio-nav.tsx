import { Home } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import UserMenu from "./user-menu";

/** Client-side navigation that App.tsx picks up via its popstate listener. */
function go(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new Event("popstate"));
}

/**
 * The consistent right-side studio nav cluster (Studio-home button + account menu), matching the
 * services hub header. Self-contained: it reads the user from AuthContext and routes via history,
 * so any module header can drop it in with no prop plumbing.
 */
export default function StudioNav({ isFrench = false }: { isFrench?: boolean }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={() => go("/services")}
        className="btn-secondary"
      >
        <Home className="h-3.5 w-3.5" aria-hidden="true" />
        {isFrench ? "Studio" : "Studio"}
      </button>
      {user && (
        <UserMenu fullName={user.full_name} role={user.role} onNavigate={go} onLogout={logout} />
      )}
    </div>
  );
}
