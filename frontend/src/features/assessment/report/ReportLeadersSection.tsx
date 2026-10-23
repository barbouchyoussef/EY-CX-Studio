import { useMemo, useState } from "react";
import { reportCopy } from "./copy";
import type { FinalReportLeadersSnapshot } from "../../../types/final-report";
import "./reportLeadersSection.css";

type Props = {
  snapshot?: FinalReportLeadersSnapshot | null;
  language?: string | null;
};


function CompanyLogo({ name, index }: { name: string; index: number }) {
  const norm = name.toLowerCase().trim();
  
  if (norm.includes("amazon")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-current" aria-hidden="true">
        <path d="M18.8 17.85c-1.9 1.4-4.7 2.2-7.5 2.2-3.8 0-7.2-1.4-9.3-3.7-.3-.3-.1-.7.3-.6 2.7.9 6.2 1.4 9.4 1.4 2.5 0 5.2-.3 7.6-1 .5-.1.8.4.5.7z"/>
        <path d="M19.7 15.6c-.2-.3-.6-.2-.8 0-.9 1-2.2 1.7-3.5 2.1-.4.1-.5.5-.2.7 1 .7 2.2.9 3.3.9.7 0 1.2-.2 1.5-.5.4-.4.3-1.1-.3-3.2z"/>
      </svg>
    );
  }
  if (norm.includes("shopify")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-current" aria-hidden="true">
        <path d="M19 6h-3c0-2.2-1.8-4-4-4S8 3.8 8 6H5c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zM12 4c1.1 0 2 .9 2 2h-4c0-1.1.9-2 2-2zm2 10h-4v-1h4v1zm2-3H8V9h8v2z"/>
      </svg>
    );
  }
  if (norm.includes("apple")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-current" aria-hidden="true">
        <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 4.17c.66-.81 1.11-1.93.99-3.06-1 .04-2.21.67-2.93 1.49-.62.69-1.16 1.84-1.01 2.96 1.12.09 2.27-.58 2.95-1.39z"/>
      </svg>
    );
  }
  if (norm.includes("airbnb")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-current" aria-hidden="true">
        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
      </svg>
    );
  }
  if (norm.includes("nike")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-current" aria-hidden="true">
        <path d="M20.2 6.5C17 9 12.5 12.5 8 16c-1.5 1.2-3.3 2.5-5 3-.5.2-1 0-.7-.4.8-1.5 2.5-4.2 4.7-7 2.2-2.8 5-5.5 8-7 .5-.3 1-.3 1 0-.1.3-.7 1.1-1.3 1.9"/>
      </svg>
    );
  }
  if (norm.includes("google")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-current" aria-hidden="true">
        <path d="M12.2 10.2v3.7h6.8c-.3 1.6-1.9 4.7-6.8 4.7-4.3 0-7.7-3.5-7.7-7.9s3.4-7.9 7.7-7.9c2.4 0 4 .9 4.9 1.8l2.9-2.8C18.1 1.8 15.4 1 12.2 1 6 1 1 6 1 12.2S6 23.4 12.2 23.4c5.8 0 11.2-4.1 11.2-11.2 0-.8-.1-1.3-.2-2H12.2z"/>
      </svg>
    );
  }
  if (norm.includes("microsoft")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[20px] w-[20px] fill-current" aria-hidden="true">
        <path d="M1 1h10v10H1zm12 0h10v10H13zM1 13h10v10H1zm12 0h10v10H13z" />
      </svg>
    );
  }
  if (norm.includes("netflix")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-current" aria-hidden="true">
        <path d="M6 4h3v16H6zm9 0h3v16h-3zm-9 0l9 16V4z" />
      </svg>
    );
  }
  if (norm.includes("spotify")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-current" aria-hidden="true">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.58 14.42c-.2.32-.62.42-.94.22-2.5-1.53-5.65-1.88-9.35-1.03-.36.08-.72-.14-.8-.5-.08-.36.14-.72.5-.8 4.05-.93 7.54-.53 10.37 1.2.32.2.42.62.22.94zm1.22-2.73c-.25.4-.77.53-1.17.28-2.86-1.76-7.22-2.27-10.6-1.24-.45.14-.92-.12-1.06-.57-.14-.45.12-.92.57-1.06 4.02-1.22 8.83-.65 12.16 1.4.4.25.53.77.28 1.17zm.1-2.85C14.48 8.7 8.78 8.5 5.44 9.5c-.52.16-1.07-.14-1.23-.66-.16-.52.14-1.07.66-1.23 3.84-1.16 10.13-.94 14.07 1.4.47.28.62.9.34 1.37-.28.47-.9.62-1.37.34z"/>
      </svg>
    );
  }
  if (norm.includes("target")) {
    return (
      <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] fill-none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="6" fill="currentColor" />
      </svg>
    );
  }

  // Thematic fallback emojis
  if (norm.includes("chase") || norm.includes("dbs") || norm.includes("ing") || norm.includes("ally") || norm.includes("allianz") || norm.includes("axa") || norm.includes("prudential") || norm.includes("ping an")) {
    return <span className="text-[1.35rem] leading-none select-none">🏦</span>;
  }
  if (norm.includes("progressive") || norm.includes("geico") || norm.includes("farm") || norm.includes("lemonade")) {
    return <span className="text-[1.35rem] leading-none select-none">🛡️</span>;
  }
  if (norm.includes("walmart") || norm.includes("sephora") || norm.includes("depot") || norm.includes("lululemon") || norm.includes("nordstrom") || norm.includes("costco") || norm.includes("best buy") || norm.includes("ebay") || norm.includes("etsy") || norm.includes("wayfair") || norm.includes("asos") || norm.includes("zalando") || norm.includes("libre") || norm.includes("alibaba")) {
    return <span className="text-[1.35rem] leading-none select-none">🛍️</span>;
  }
  if (norm.includes("verizon") || norm.includes("vodafone") || norm.includes("telstra") || norm.includes("orange") || norm.includes("mobile") || norm.includes("swisscom")) {
    return <span className="text-[1.35rem] leading-none select-none">📱</span>;
  }
  if (norm.includes("permanente") || norm.includes("clinic") || norm.includes("unitedhealth") || norm.includes("cvs") || norm.includes("oscar") || norm.includes("doctor") || norm.includes("medical")) {
    return <span className="text-[1.35rem] leading-none select-none">🏥</span>;
  }
  if (norm.includes("marriott") || norm.includes("delta") || norm.includes("booking") || norm.includes("tripadvisor") || norm.includes("airlines") || norm.includes("hilton")) {
    return <span className="text-[1.35rem] leading-none select-none">✈️</span>;
  }
  if (norm.includes("gov") || norm.includes("usps") || norm.includes("singpass") || norm.includes("nhs") || norm.includes("estonia") || norm.includes("service nsw")) {
    return <span className="text-[1.35rem] leading-none select-none">🏛️</span>;
  }
  if (norm.includes("salesforce") || norm.includes("adobe") || norm.includes("slack") || norm.includes("zoom")) {
    return <span className="text-[1.35rem] leading-none select-none">💻</span>;
  }

  const fallbackEmojis = ["🧭", "🌍", "🎟️", "📊"];
  const emoji = fallbackEmojis[index % fallbackEmojis.length];
  return <span className="text-[1.35rem] leading-none select-none">{emoji}</span>;
}

function getCompanyStyle(name: string) {
  const norm = name.toLowerCase().trim();
  
  if (norm.includes("amazon")) {
    return {
      gradient: "linear-gradient(135deg, #FFB834 0%, #FF9900 100%)",
      shadow: "0 12px 24px rgba(255, 153, 0, 0.28)",
      activeBorder: "rgba(255, 153, 0, 0.35)",
      activeShadow: "0 16px 36px rgba(255, 153, 0, 0.16)"
    };
  }
  if (norm.includes("shopify")) {
    return {
      gradient: "linear-gradient(135deg, #B1E059 0%, #7AAB38 100%)",
      shadow: "0 12px 24px rgba(122, 171, 56, 0.28)",
      activeBorder: "rgba(150, 191, 72, 0.35)",
      activeShadow: "0 16px 36px rgba(150, 191, 72, 0.16)"
    };
  }
  if (norm.includes("apple")) {
    return {
      gradient: "linear-gradient(135deg, #fbfbfb 0%, #8c8c8c 100%)",
      shadow: "0 12px 24px rgba(255, 255, 255, 0.16)",
      activeBorder: "rgba(255, 255, 255, 0.25)",
      activeShadow: "0 16px 36px rgba(255, 255, 255, 0.1)"
    };
  }
  if (norm.includes("airbnb")) {
    return {
      gradient: "linear-gradient(135deg, #FF7C80 0%, #FF5A5F 100%)",
      shadow: "0 12px 24px rgba(255, 90, 95, 0.28)",
      activeBorder: "rgba(255, 90, 95, 0.35)",
      activeShadow: "0 16px 36px rgba(255, 90, 95, 0.16)"
    };
  }
  if (norm.includes("nike")) {
    return {
      gradient: "linear-gradient(135deg, #555555 0%, #111111 100%)",
      shadow: "0 12px 24px rgba(255, 255, 255, 0.14)",
      activeBorder: "rgba(255, 255, 255, 0.22)",
      activeShadow: "0 16px 36px rgba(255, 255, 255, 0.08)"
    };
  }
  if (norm.includes("google")) {
    return {
      gradient: "linear-gradient(135deg, #4285F4 0%, #34A853 100%)",
      shadow: "0 12px 24px rgba(66, 133, 244, 0.28)",
      activeBorder: "rgba(66, 133, 244, 0.35)",
      activeShadow: "0 16px 36px rgba(66, 133, 244, 0.16)"
    };
  }
  if (norm.includes("microsoft")) {
    return {
      gradient: "linear-gradient(135deg, #00A4EF 0%, #7FBA00 100%)",
      shadow: "0 12px 24px rgba(0, 164, 239, 0.28)",
      activeBorder: "rgba(0, 164, 239, 0.35)",
      activeShadow: "0 16px 36px rgba(0, 164, 239, 0.16)"
    };
  }
  if (norm.includes("netflix")) {
    return {
      gradient: "linear-gradient(135deg, #ff1e27 0%, #b20710 100%)",
      shadow: "0 12px 24px rgba(229, 9, 20, 0.28)",
      activeBorder: "rgba(229, 9, 20, 0.35)",
      activeShadow: "0 16px 36px rgba(229, 9, 20, 0.16)"
    };
  }
  if (norm.includes("spotify")) {
    return {
      gradient: "linear-gradient(135deg, #29d85d 0%, #1db954 100%)",
      shadow: "0 12px 24px rgba(29, 185, 84, 0.28)",
      activeBorder: "rgba(29, 185, 84, 0.35)",
      activeShadow: "0 16px 36px rgba(29, 185, 84, 0.16)"
    };
  }
  if (norm.includes("target")) {
    return {
      gradient: "linear-gradient(135deg, #ff4c4c 0%, #cc0000 100%)",
      shadow: "0 12px 24px rgba(204, 0, 0, 0.28)",
      activeBorder: "rgba(204, 0, 0, 0.35)",
      activeShadow: "0 16px 36px rgba(204, 0, 0, 0.16)"
    };
  }

  // Thematic sectors
  if (norm.includes("chase") || norm.includes("dbs") || norm.includes("ing") || norm.includes("ally") || norm.includes("allianz") || norm.includes("axa") || norm.includes("prudential") || norm.includes("ping an")) {
    return {
      gradient: "linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)",
      shadow: "0 12px 24px rgba(2, 132, 199, 0.22)",
      activeBorder: "rgba(2, 132, 199, 0.32)",
      activeShadow: "0 16px 36px rgba(2, 132, 199, 0.14)"
    };
  }
  if (norm.includes("progressive") || norm.includes("geico") || norm.includes("farm") || norm.includes("lemonade")) {
    return {
      gradient: "linear-gradient(135deg, #fbbf24 0%, #d97706 100%)",
      shadow: "0 12px 24px rgba(217, 119, 6, 0.22)",
      activeBorder: "rgba(217, 119, 6, 0.32)",
      activeShadow: "0 16px 36px rgba(217, 119, 6, 0.14)"
    };
  }
  if (norm.includes("walmart") || norm.includes("sephora") || norm.includes("depot") || norm.includes("lululemon") || norm.includes("nordstrom") || norm.includes("costco") || norm.includes("best buy") || norm.includes("ebay") || norm.includes("etsy") || norm.includes("wayfair") || norm.includes("asos") || norm.includes("zalando") || norm.includes("libre") || norm.includes("alibaba")) {
    return {
      gradient: "linear-gradient(135deg, #fb923c 0%, #ea580c 100%)",
      shadow: "0 12px 24px rgba(234, 88, 12, 0.22)",
      activeBorder: "rgba(234, 88, 12, 0.32)",
      activeShadow: "0 16px 36px rgba(234, 88, 12, 0.14)"
    };
  }
  if (norm.includes("verizon") || norm.includes("vodafone") || norm.includes("telstra") || norm.includes("orange") || norm.includes("mobile") || norm.includes("swisscom")) {
    return {
      gradient: "linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%)",
      shadow: "0 12px 24px rgba(124, 58, 237, 0.22)",
      activeBorder: "rgba(124, 58, 237, 0.32)",
      activeShadow: "0 16px 36px rgba(124, 58, 237, 0.14)"
    };
  }
  if (norm.includes("permanente") || norm.includes("clinic") || norm.includes("unitedhealth") || norm.includes("cvs") || norm.includes("oscar") || norm.includes("doctor") || norm.includes("medical")) {
    return {
      gradient: "linear-gradient(135deg, #f87171 0%, #dc2626 100%)",
      shadow: "0 12px 24px rgba(220, 38, 38, 0.22)",
      activeBorder: "rgba(220, 38, 38, 0.32)",
      activeShadow: "0 16px 36px rgba(220, 38, 38, 0.14)"
    };
  }
  if (norm.includes("marriott") || norm.includes("delta") || norm.includes("booking") || norm.includes("tripadvisor") || norm.includes("airlines") || norm.includes("hilton")) {
    return {
      gradient: "linear-gradient(135deg, #34d399 0%, #059669 100%)",
      shadow: "0 12px 24px rgba(5, 150, 105, 0.22)",
      activeBorder: "rgba(5, 150, 105, 0.32)",
      activeShadow: "0 16px 36px rgba(5, 150, 105, 0.14)"
    };
  }
  if (norm.includes("gov") || norm.includes("usps") || norm.includes("singpass") || norm.includes("nhs") || norm.includes("estonia") || norm.includes("service nsw")) {
    return {
      gradient: "linear-gradient(135deg, #94a3b8 0%, #475569 100%)",
      shadow: "0 12px 24px rgba(71, 85, 105, 0.22)",
      activeBorder: "rgba(71, 85, 105, 0.32)",
      activeShadow: "0 16px 36px rgba(71, 85, 105, 0.14)"
    };
  }

  return {
    gradient: "linear-gradient(135deg, #85eaff 0%, #00d4ff 100%)",
    shadow: "0 12px 24px rgba(0, 212, 255, 0.22)",
    activeBorder: "rgba(0, 212, 255, 0.32)",
    activeShadow: "0 16px 36px rgba(0, 212, 255, 0.14)"
  };
}

export default function ReportLeadersSection({ snapshot, language }: Props) {
  const leaders = snapshot?.leaders ?? [];
  const logoSrc = `${import.meta.env.BASE_URL}EY_Studio+_Logo_Primary_WithoutStrapline_RGB_White_Yellow_Grad_EN.png`;

  const competitorLeaders = useMemo(
    () => leaders.filter((l) => l.key !== "ey-insights"),
    [leaders]
  );

  const eyLeader = useMemo(
    () => leaders.find((l) => l.key === "ey-insights"),
    [leaders]
  );

  const [selectedKey, setSelectedKey] = useState<string>("");
  const [pptxModalUrl, setPptxModalUrl] = useState<string | null>(null);

  const handleLinkClick = (e: React.MouseEvent<HTMLAnchorElement>, url: string) => {
    if (url.toLowerCase().endsWith(".pptx")) {
      e.preventDefault();
      const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
      if (isLocal) {
        setPptxModalUrl(url);
      } else {
        const previewUrl = `https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(window.location.origin + url)}`;
        window.open(previewUrl, "_blank");
      }
    }
  };

  // No effect resets the selection here. `selectedLeader` below already falls back to the first
  // leader when the chosen key is not in the list, which covers the data changing -- while an
  // effect would also fire on a re-render that merely handed down a new array, throwing away a
  // selection the reader had made.

  const selectedLeader = useMemo(
    () => competitorLeaders.find((leader) => leader.key === selectedKey) ?? competitorLeaders[0] ?? null,
    [competitorLeaders, selectedKey],
  );

  if (!snapshot) {
    return null;
  }

  const isFrench = (language ?? "").toLowerCase().startsWith("fr");
  const copy = reportCopy(isFrench);
  const isPending = snapshot.status === "pending" || snapshot.status === "running";
  const emptyMessage =
    snapshot.message ??
    (isPending
      ? (copy.leadersPreparing)
      : (copy.leadersUnavailable));

  return (
    <div className="report-leaders-shell">
      <section className="section">
        <div className="orbital-ring" aria-hidden="true"></div>
        <div className="orbital-ring-small" aria-hidden="true"></div>
        <div className="orbital-ring-left" aria-hidden="true"></div>

        <div className="section-head">
          <span className="section-number">04</span>
          <h1 className="section-title">
            {copy.leadersTitle}
          </h1>
        </div>

        <div className="panel">
          <div className="panel-inner">
            <div className="content-shell print:hidden">
              <div className="content-stage active" data-stage="leaders">
                <div className="stage-meta">
                  <div className="stage-summary">
                    <h3 className="stage-heading">
                      {copy.leadersLead}
                    </h3>
                  </div>
                </div>

                {competitorLeaders.length ? (
                  <>
                    <div className="chip-grid">
                      {competitorLeaders.map((leader, index) => {
                        const style = getCompanyStyle(leader.company_name);
                        const isActive = leader.key === (selectedLeader?.key ?? "");
                        const activeStyle = isActive
                          ? {
                              borderColor: style.activeBorder,
                              boxShadow: style.activeShadow,
                            }
                          : {};

                        return (
                          <button
                            key={leader.key}
                            className={`comp-chip ${isActive ? "active" : ""}`}
                            style={activeStyle}
                            type="button"
                            data-competitor={leader.key}
                            onClick={() => setSelectedKey(leader.key)}
                          >
                            <div className="chip-head">
                              <div
                                className="chip-logo-container"
                                style={{
                                  background: style.gradient,
                                  boxShadow: style.shadow,
                                }}
                              >
                                <CompanyLogo name={leader.company_name} index={index} />
                              </div>
                            </div>
                            <p className="chip-name">{leader.company_name}</p>
                            <p className="chip-note">
                              {leader.leader_summary ??
                                leader.note ??
                                (copy.leaderEvidenceNote)}
                            </p>
                          </button>
                        );
                      })}
                    </div>

                    <div className="drawer" data-drawer="leaders">
                      <div className="drawer-head">
                        <h4 className="drawer-name">{selectedLeader?.company_name ?? ""}</h4>
                      </div>
                      <p className="drawer-title">{copy.leadersSubheading}</p>
                      <div className="practice-list">
                        {(selectedLeader?.evidence_links ?? []).map((link, index) => (
                          <div key={`${selectedLeader?.key ?? "leader"}-${index}`} className="practice">
                            <span className="practice-copy">{link.label}</span>
                            <a
                              className="practice-link"
                              href={link.url}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => handleLinkClick(e, link.url)}
                            >
                              {link.source_title
                                ? isFrench
                                  ? `Source ouverte : ${link.source_title}`
                                  : `Open source: ${link.source_title}`
                                : copy.openSource}
                            </a>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="drawer" data-drawer="leaders">
                    <p className="empty-state">{emptyMessage}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="print-leaders-list hidden">
              {competitorLeaders.length ? (
                competitorLeaders.map((leader, index) => {
                  const style = getCompanyStyle(leader.company_name);
                  return (
                    <section key={`print-${leader.key}`} className="print-leader-card">
                      <div className="chip-head" style={{ marginBottom: "12px" }}>
                        <div
                          className="chip-logo-container"
                          style={{
                            background: style.gradient,
                            boxShadow: style.shadow,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: "44px",
                            height: "44px",
                            borderRadius: "14px",
                            color: "#fff"
                          }}
                        >
                          <CompanyLogo name={leader.company_name} index={index} />
                        </div>
                      </div>
                      <h4 className="drawer-name">{leader.company_name}</h4>
                      <p className="chip-note" style={{ color: "rgba(255,255,255,0.7)" }}>
                        {leader.leader_summary ?? leader.note ?? (copy.leaderEvidenceNote)}
                      </p>
                    <div className="practice-list">
                      {(leader.evidence_links ?? []).map((link, linkIndex) => (
                        <div key={`${leader.key}-print-${linkIndex}`} className="practice">
                          <span className="practice-copy">{link.label}</span>
                          <a className="practice-link" href={link.url} target="_blank" rel="noreferrer">
                            {link.source_title
                              ? isFrench
                                ? `Source ouverte : ${link.source_title}`
                                : `Open source: ${link.source_title}`
                              : copy.openSource}
                          </a>
                        </div>
                      ))}
                    </div>
                  </section>
                );
              })
              ) : (
                <div className="drawer">
                  <p className="empty-state">{emptyMessage}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {eyLeader && (
          <div className="ey-insights-wrapper print:page-break-inside-avoid">
            <div className="ey-insights-header">
              <img src={logoSrc} alt="EY Logo" className="ey-insights-brand-logo" />
              <div className="ey-insights-title-block">
                <p className="ey-insights-pre">{copy.exclusiveThoughtLeadership}</p>
                <h3 className="ey-insights-title">{eyLeader.company_name}</h3>
              </div>
            </div>
            <div className="ey-insights-body">
              <p className="ey-insights-summary">{eyLeader.leader_summary}</p>
              <div className="ey-insights-links-grid">
                {(eyLeader.evidence_links ?? []).map((link, index) => (
                  <a
                    key={`ey-link-${index}`}
                    className="ey-link-card"
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => handleLinkClick(e, link.url)}
                  >
                    <div>
                      <h4 className="ey-link-label">{link.label}</h4>
                      <p className="ey-link-desc">{link.why_relevant}</p>
                    </div>
                    <div className="ey-link-footer">
                      <span>{copy.readEyArticle}</span>
                      <span className="ey-link-arrow">→</span>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Local Preview Modal for PPTX on localhost */}
      {pptxModalUrl && (
        <div 
          className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 backdrop-blur-xl p-4 transition-all duration-300"
          onClick={() => setPptxModalUrl(null)}
        >
          <div 
            className="w-full max-w-md bg-[linear-gradient(180deg,rgba(255,255,255,0.07),rgba(255,255,255,0.025)),rgba(9,12,22,0.98)] border border-white/10 rounded-[28px] p-8 shadow-[0_24px_64px_rgba(0,0,0,0.5)] text-white"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3.5 mb-5">
              <span className="text-[28px]">📊</span>
              <div>
                <span className="font-mono text-[0.7rem] text-white/50 uppercase tracking-[0.2em]">
                  {copy.deckPreviewTitle}
                </span>
                <h3 className="text-xl font-bold tracking-tight text-white m-0 mt-0.5">
                  {copy.deckLocalTitle}
                </h3>
              </div>
            </div>

            <p className="text-sm leading-relaxed text-slate-300 mb-6 m-0">
              {copy.deckLocalLead}
            </p>

            <div className="flex flex-col gap-3">
              <a
                href={pptxModalUrl}
                download
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[linear-gradient(135deg,#ffd447_0%,#c8973f_100%)] px-5 py-3.5 text-sm font-bold text-[#111318] shadow-[0_12px_26px_rgba(200,151,63,0.28)] transition-all hover:translate-y-[-2px]"
                onClick={() => setPptxModalUrl(null)}
              >
                {copy.deckDownload}
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
              </a>
              <button
                type="button"
                className="inline-flex w-full items-center justify-center rounded-xl bg-white/5 border border-white/10 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:bg-white/10 hover:text-white"
                onClick={() => setPptxModalUrl(null)}
              >
                {copy.close}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
