import type { FinalReportWorkingMissingItem } from "../../../types/final-report";
import { reportCopy } from "./copy";
import { capabilityLinks } from "../../../config/capabilityLinks";
import { getBandClass, getMaturityBandDisplayName } from "../../../utils/reportHelpers";

type ModalState = {
  item: FinalReportWorkingMissingItem;
  status: "working" | "missing";
  axisLabel: string;
} | null;

type Props = {
  item: FinalReportWorkingMissingItem;
  status: "working" | "missing";
  axisLabel: string;
  onOpen: (state: ModalState) => void;
  isFrench?: boolean;
};

export default function CapabilityButton({
  item,
  status,
  axisLabel,
  onOpen,
  isFrench,
}: Props) {
  const copy = reportCopy(Boolean(isFrench));
  const linkColor = status === "working" ? "text-emerald-400 hover:text-emerald-300" : "text-rose-400 hover:text-rose-300";

  return (
    <div 
      className="cap-pill group relative cursor-pointer" 
      onClick={() => onOpen({ item, status, axisLabel })}
      role="button"
      tabIndex={0}
    >
      <div className="cap-pill-top">
        <p className="cap-pill-name">{item.capability}</p>
        <span className={`cap-tag ${getBandClass(item.maturity_band)}`}>{getMaturityBandDisplayName(item.maturity_band, isFrench)}</span>
      </div>
      <p className="cap-pill-summary">{item.summary}</p>
      
      {capabilityLinks[item.capability] ? (
        <div className="mt-3">
          <a
            href={capabilityLinks[item.capability]}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className={`inline-flex items-center gap-1.5 text-[13px] font-semibold transition ${linkColor}`}
          >
            {copy.referenceGuide}
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="transition-transform duration-200 group-hover:translate-x-0.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
          </a>
        </div>
      ) : null}
    </div>
  );
}
