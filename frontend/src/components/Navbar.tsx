import { useEffect, useState } from "react";
import { pickCopy } from "../lib/i18n";
import "./Navbar.css";
import UserMenu from "./ui/user-menu";

type NavbarProps = {
  onStartConversation?: () => void;
  language?: string;
  onLanguageChange?: (lang: string) => void;
  user?: { full_name: string; role: string } | null;
  onNavigate?: (path: string) => void;
  onLogout?: () => void;
};

const TRANSLATIONS = {
  fr: {
    brandTitle: "CX Studio",
    howItWorks: "Capacités",
    analysis: "Cas d'usage",
    cta: "Ouvrir le Studio",
  },
  en: {
    brandTitle: "CX Studio",
    howItWorks: "Capabilities",
    analysis: "Use cases",
    cta: "Open the Studio",
  },
};

export default function Navbar({ onStartConversation, language = "en", onLanguageChange, user, onNavigate, onLogout }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);
  const logoSrc = `${import.meta.env.BASE_URL}ey_logo.svg`;
  const t = pickCopy(TRANSLATIONS, language);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav className={`nav ${scrolled ? "scrolled" : ""}`} id="nav">
      <div className="nav__inner">
        <div className="nav__brand">
          <img src={logoSrc} alt="EY Studio+" className="nav__logo" />
          <span className="nav__separator">|</span>
          <span className="nav__title">{t.brandTitle}</span>
        </div>

        <div className="nav__links">
          <a href="#capabilities" className="nav__link">
            {t.howItWorks}
          </a>
          <a href="#use-cases" className="nav__link">
            {t.analysis}
          </a>
          <button type="button" className="nav__cta" onClick={onStartConversation}>
            {t.cta}
          </button>
        </div>

        <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-white/80 p-0.5 shadow-sm backdrop-blur ml-auto lg:ml-6">
          <button
            type="button"
            onClick={() => onLanguageChange?.("fr")}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-all duration-200 ${language === "fr" ? "bg-ink text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
          >
            FR
          </button>
          <button
            type="button"
            onClick={() => onLanguageChange?.("en")}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-all duration-200 ${language === "en" ? "bg-ink text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
          >
            EN
          </button>
        </div>

        {user && onNavigate && onLogout && (
          <div className="ml-3">
            <UserMenu
              fullName={user.full_name}
              role={user.role}
              onNavigate={onNavigate}
              onLogout={onLogout}
            />
          </div>
        )}
      </div>
    </nav>
  );
}
