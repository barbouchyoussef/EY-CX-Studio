import { useEffect, useState, lazy, Suspense } from "react";
import { useAuth } from "./context/AuthContext";
import { LoginPage, AcceptInvitePage, ForgotPasswordPage, ResetPasswordPage, ChangePasswordPage } from "./features/auth";
import { AdminUsersPage } from "./features/admin";
import { ProjectStepNav } from "./features/projects";
import type { StepKey } from "./lib/projectsApi";
import NavBar from "./components/Navbar";
import InternalHome from "./components/InternalHome";
import Footer from "./components/Footer";

/** The path the browser loaded this document on, captured once and never updated.
 *
 *  In-app navigation rewrites `pathname` via pushState, so by the time a lazy module runs its own
 *  top-level code it can no longer tell how it was reached. This constant can: a reload lands the
 *  document directly on the module's route, while opening a module from the services hub happens
 *  inside a document that loaded somewhere else entirely.
 */
const LOADED_PATHNAME = typeof window === "undefined" ? "" : window.location.pathname;

// Lazy-loaded sub-pages to optimize initial landing bundle size
const AssessmentChatStatic = lazy(() => import("./features/assessment").then((m) => ({ default: m.AssessmentChat })));
const ClientAssessmentPage = lazy(() => import("./features/assessment").then((m) => ({ default: m.ClientAssessmentPage })));
const AdminDashboard = lazy(() => import("./features/admin").then((m) => ({ default: m.AdminDashboard })));
const AdminAssessmentDetail = lazy(() => import("./features/admin").then((m) => ({ default: m.AdminAssessmentDetail })));
const AdminAssessmentReport = lazy(() => import("./features/admin").then((m) => ({ default: m.AdminAssessmentReport })));
const ClientInterviewHub = lazy(() => import("./features/interview"));
const SocialScraping = lazy(() => import("./features/social"));
const DeskResearch = lazy(() => import("./features/desk-research"));
const ServicesHub = lazy(() => import("./features/projects").then((m) => ({ default: m.ServicesHub })));
const IssueLogPage = lazy(() => import("./features/issue-log"));

function RouteLoader() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-[#0F1015]">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="relative h-12 w-12">
          {/* Outer elegant spinning gradient ring */}
          <div className="absolute inset-0 rounded-full border-2 border-t-ey-gold border-r-transparent border-b-ey-blue border-l-transparent animate-spin" />
          {/* Inner pulse */}
          <div className="absolute inset-2 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(197,160,79,0.9),rgba(56,88,233,0.4))] animate-pulse" />
        </div>
        <div className="text-[10px] font-medium uppercase tracking-[0.25em] text-[#A0AEC0]/60 animate-pulse">
          Loading
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [language, setLanguage] = useState<string>("en");
  const [adminView, setAdminView] = useState<"dashboard" | "details" | "report" | "interview-guide">("dashboard");
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<number | null>(null);
  const [pathname, setPathname] = useState(() => (typeof window === "undefined" ? "/" : window.location.pathname));

  useEffect(() => {
    const onPopState = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const showAdmin = pathname.startsWith("/admin");
  const showInterviewHub = pathname.startsWith("/client-interview-hub") || pathname.startsWith("/interview-hub");
  const showSocialScraping = pathname.startsWith("/social-scraping");
  const showDeskResearch = pathname.startsWith("/desk-research");
  const showAssessment = pathname.startsWith("/assessment");
  const showServicesHub = pathname.startsWith("/services");
  const showIssueLog = pathname.startsWith("/issue-log");

  const navigateTo = (path: string) => {
    window.history.pushState({}, "", path);
    setPathname(path);
  };

  // ── Auth gate ──────────────────────────────────────────────────────────────
  // The WHOLE platform requires a session -- including the marketing landing. The only
  // routes reachable while signed out are the auth screens themselves.
  const { user, loading: authLoading, logout } = useAuth();

  // Public, passwordless client route: `/a/<token>`. Fully outside the auth gate — a client opens
  // this with only the link token, no account. Must be checked before any login redirect.
  if (pathname.startsWith("/a/")) {
    const token = decodeURIComponent(pathname.slice(3));
    return (
      <Suspense fallback={<RouteLoader />}>
        <ClientAssessmentPage token={token} />
      </Suspense>
    );
  }

  const showAcceptInvite = pathname.startsWith("/accept-invite");
  const showForgot = pathname.startsWith("/forgot-password");
  const showReset = pathname.startsWith("/reset-password");
  const showChangePw = pathname === "/account";
  const showManageUsers = pathname === "/manage-users";

  // Public auth screens (the only things reachable without a session).
  if (showAcceptInvite) {
    return <AcceptInvitePage onSuccess={() => navigateTo("/services")} />;
  }
  if (showReset) {
    return <ResetPasswordPage onSuccess={() => navigateTo("/services")} />;
  }
  if (showForgot) {
    return <ForgotPasswordPage onBack={() => navigateTo("/login")} />;
  }
  // Don't flash the login screen while the initial silent refresh is still resolving.
  if (authLoading) {
    return <RouteLoader />;
  }
  // Not signed in -> the whole platform is behind login. After sign-in, land on the homepage.
  if (!user) {
    return (
      <LoginPage
        onSuccess={() => navigateTo("/")}
        onForgot={() => navigateTo("/forgot-password")}
      />
    );
  }

  const handleLogout = () => {
    logout();
    navigateTo("/");
  };

  // Floating "working in a project" bar, shown over any module. Renders nothing when no project
  // is active, so it's safe to include in every module route.
  const currentStep: StepKey | null = showAssessment
    ? "assessment"
    : showInterviewHub
      ? "interview"
      : showDeskResearch
        ? "desk_research"
        : showSocialScraping
          ? "social"
          : null;
  const projectBar = (
    <ProjectStepNav currentStep={currentStep} onNavigate={navigateTo} isFrench={language === "fr"} />
  );

  // Authenticated account screens.
  if (showChangePw) {
    return <ChangePasswordPage onBack={() => navigateTo("/")} />;
  }
  if (showManageUsers) {
    if (user?.role !== "admin") {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[linear-gradient(180deg,#ffffff_0%,#f7f9fb_100%)] text-slate-600">
          <p className="text-sm">You don’t have access to this page.</p>
          <button
            onClick={() => navigateTo("/")}
            className="rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-white hover:bg-ink-hover"
          >
            Back to studio
          </button>
        </div>
      );
    }
    return <AdminUsersPage onBack={() => navigateTo("/")} />;
  }

  if (showInterviewHub) {
    return (
      <Suspense fallback={<RouteLoader />}>
        <ClientInterviewHub onBack={() => navigateTo("/services")} topSlot={projectBar} />
      </Suspense>
    );
  }

  if (showSocialScraping) {
    return (
      <Suspense fallback={<RouteLoader />}>
        <SocialScraping onBack={() => navigateTo("/services")} topSlot={projectBar} />
      </Suspense>
    );
  }

  if (showDeskResearch) {
    return (
      <Suspense fallback={<RouteLoader />}>
        <DeskResearch onBack={() => navigateTo("/services")} topSlot={projectBar} />
      </Suspense>
    );
  }

  if (showIssueLog) {
    return (
      <Suspense fallback={<RouteLoader />}>
        <IssueLogPage onBack={() => navigateTo("/services")} topSlot={projectBar} />
      </Suspense>
    );
  }

  if (showServicesHub) {
    return (
      <Suspense fallback={<RouteLoader />}>
        <ServicesHub
          language={language}
          user={user}
          onNavigate={navigateTo}
          onLogout={handleLogout}
          onBack={() => navigateTo("/")}
          onOpenAssessment={() => navigateTo("/assessment")}
          onOpenInterviewHub={() => navigateTo("/client-interview-hub")}
          onOpenSocialScraping={() => navigateTo("/social-scraping")}
          onOpenDeskResearch={() => navigateTo("/desk-research")}
        />
      </Suspense>
    );
  }

  if (showAdmin) {
    return (
      <Suspense fallback={<RouteLoader />}>
        {adminView === "details" && selectedAssessmentId ? (
          <AdminAssessmentDetail assessmentId={selectedAssessmentId} onBack={() => setAdminView("dashboard")} />
        ) : adminView === "report" && selectedAssessmentId ? (
          <AdminAssessmentReport assessmentId={selectedAssessmentId} onBack={() => setAdminView("dashboard")} />
        ) : (
          <AdminDashboard
            onBack={() => {
              window.history.pushState({}, "", "/");
              setPathname("/");
            }}
            onOpenAssessmentDetails={(assessmentId) => {
              setSelectedAssessmentId(assessmentId);
              setAdminView("details");
            }}
            onOpenAssessmentReport={(assessmentId) => {
              setSelectedAssessmentId(assessmentId);
              setAdminView("report");
            }}
          />
        )}
      </Suspense>
    );
  }

  if (showAssessment) {
    return (
      <Suspense fallback={<RouteLoader />}>
        <AssessmentChatStatic
          onBack={() => window.history.back()}
          language={language}
          topSlot={projectBar}
          resumeLastConversation={LOADED_PATHNAME.startsWith("/assessment")}
        />
      </Suspense>
    );
  }

  return (
    <>
      <NavBar
        onStartConversation={() => navigateTo("/services")}
        language={language}
        onLanguageChange={setLanguage}
        user={user}
        onNavigate={navigateTo}
        onLogout={handleLogout}
      />
      {/* The nav is fixed, so main reserves its exact height: .nav__inner 64px + the 1px
          border-bottom. It was 80px, and the extra 15px let the body background show through
          as a grey band under the nav. Vertical breathing room is the hero's own py-20. */}
      <main style={{ paddingTop: "65px" }}>
        <InternalHome onOpenServices={() => navigateTo("/services")} language={language} />
        <Footer language={language} mvpNote />
      </main>
    </>
  );
}
