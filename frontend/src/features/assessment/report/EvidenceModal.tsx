import type { FinalReportWorkingMissingItem } from "../../../types/final-report";
import { reportCopy } from "./copy";
import { capabilityLinks } from "../../../config/capabilityLinks";

type ModalState = {
  item: FinalReportWorkingMissingItem;
  status: "working" | "missing";
  axisLabel: string;
} | null;

type Props = {
  modalState: ModalState;
  onClose: () => void;
  isFrench: boolean;
};

export default function EvidenceModal({ modalState, onClose, isFrench }: Props) {
  const copy = reportCopy(isFrench);
  if (!modalState) return null;

  return (
    <div
      className="modal open"
      id="evidence-modal"
      aria-hidden="false"
      onClick={onClose}
    >
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <div className="modal-overline" id="modal-overline">
              {isFrench
                ? `Axe ${modalState.axisLabel} | ${modalState.status === "working" ? "Ce qui fonctionne" : "Ce qui manque"}`
                : `${modalState.axisLabel} axis | ${modalState.status === "working" ? "Working" : "Missing"}`}
            </div>
            <h2 className="modal-title" id="modal-title">
              {modalState.item.capability}
            </h2>
          </div>
          <button className="modal-close" id="close-modal" type="button" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <div className="modal-evidence-list" id="modal-evidence-list">
            <div className="evidence-item">
              <p className="evidence-quote">
                {modalState.item.evidence_snippet || modalState.item.summary || ""}
              </p>
              {modalState.item.capability && capabilityLinks[modalState.item.capability] ? (
                <div className="mt-5">
                  <a 
                    href={capabilityLinks[modalState.item.capability]} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-white/5 border border-white/10 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:bg-white/10 hover:text-white"
                  >
                    {copy.viewReferenceGuide}
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                  </a>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
