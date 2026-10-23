import { useEffect, useState, useMemo } from "react";
import { reportCopy } from "./copy";

import type { FinalReportQuickWinItem, FinalReportQuickWinsTimeline } from "../../../types/final-report";
import "./reportQuickWinsTimeline.css";

type Props = {
  timeline?: FinalReportQuickWinsTimeline | null;
  language?: string | null;
};

const ORBIT_IMAGE_SRC = "/d87248c323a11fe6364ab034b73bea1e1c1e77f7.png";

function fallbackTitle(item: FinalReportQuickWinItem) {
  return item.title?.trim() || `Quick win ${item.step}`;
}

export default function ReportQuickWinsTimeline({ timeline, language }: Props) {
  const items = useMemo(() => timeline?.items?.slice(0, 4) ?? [], [timeline?.items]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const isFrench = (language ?? timeline?.language ?? "").toLowerCase().startsWith("fr");
  const copy = reportCopy(isFrench);
  const labels = {
    owner: copy.quickWinOwner,
    today: copy.quickWinToday,
    after: copy.quickWinAfter,
    close: copy.quickWinClose,
    open: copy.quickWinOpen,
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  if (!timeline || items.length === 0) {
    return null;
  }

  const activeItem = items[activeIndex] ?? items[0];

  return (
    <section className="report-quick-wins-shell relative overflow-hidden px-3 py-4 text-white sm:px-6 sm:py-6 lg:px-10 lg:py-8 print:px-0 print:py-0">
      <div className="section">
        <div className="orbital-ring" />
        <div className="orbital-ring-small" />
        <div className="orbital-ring-left" />

        <div className="section-head">
          <span className="section-number">05</span>
          <h2 className="section-title">{timeline.section_title}</h2>
        </div>

        <div className="stage-shell">
          <div className="orbital-visual" aria-hidden="true">
            <img src={ORBIT_IMAGE_SRC} alt="" />
          </div>

          <div className="timeline-stage">
            <div className="timeline-connectors" aria-hidden="true">
              <div className="timeline-connector-segment seg-1" />
              <div className="timeline-connector-segment seg-2" />
              <div className="timeline-connector-segment seg-3" />
            </div>

            {items.map((item, index) => {
              const side = index % 2 === 0 ? "left" : "right";
              return (
                <div key={`${item.step}-${index}`} className={`timeline-node step-${index + 1}`} data-side={side}>
                  <div className="label-box">
                    <div className="label-time">{item.timeline_label}</div>
                    <div className="label-title">{fallbackTitle(item)}</div>
                  </div>
                  <div className="dot-wrap">
                    <button
                      className={`timeline-dot ${activeIndex === index ? "is-active" : ""}`}
                      type="button"
                      aria-label={`${labels.open} ${item.step}`}
                      onClick={() => {
                        setActiveIndex(index);
                        setIsOpen(true);
                      }}
                    >
                      {item.step}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="print-quick-wins-list hidden">
            {items.map((item) => (
              <article key={`print-qw-${item.step}`} className="print-quick-win-card">
                <div className="label-time">{item.timeline_label}</div>
                <h3 className="qw-title mt-2">{fallbackTitle(item)}</h3>
                <div className="qw-owner-chip mt-3">{labels.owner} | {item.owner}</div>
                <div className="ba-grid mt-4">
                  <div className="ba-cell before">
                    <div className="ba-label">{labels.today}</div>
                    <div className="ba-text">{item.today_text}</div>
                  </div>
                  <div className="ba-cell after">
                    <div className="ba-label">{labels.after}</div>
                    <div className="ba-text">{item.after_text}</div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div
          className={`detail-popup ${isOpen ? "is-visible" : ""}`}
          aria-hidden={isOpen ? "false" : "true"}
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setIsOpen(false);
            }
          }}
        >
          {activeItem ? (
            <div className="detail-popup-card" role="dialog" aria-modal="true" aria-labelledby="quick-win-title">
              <article className="qw-card">
                <div className="qw-card-top">
                  <div className="qw-num">{activeItem.step}</div>
                  <div>
                    <h3 className="qw-title" id="quick-win-title">
                      {fallbackTitle(activeItem)}
                    </h3>
                    <div className="qw-owner-chip">{labels.owner} | {activeItem.owner}</div>
                  </div>
                  <button className="qw-close" type="button" aria-label={labels.close} onClick={() => setIsOpen(false)}>
                    X
                  </button>
                </div>
                <div className="qw-body">
                  <div className="ba-grid">
                    <div className="ba-cell before">
                      <div className="ba-label">{labels.today}</div>
                      <div className="ba-text">{activeItem.today_text}</div>
                    </div>
                    <div className="ba-cell after">
                      <div className="ba-label">{labels.after}</div>
                      <div className="ba-text">{activeItem.after_text}</div>
                    </div>
                  </div>
                </div>
              </article>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
