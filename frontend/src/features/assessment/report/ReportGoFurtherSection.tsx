import { useState, type FormEvent } from "react";
import { reportCopy } from "./copy";
import "./reportGoFurtherSection.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
const STUDIO_LOGO_SRC = "/EY_Studio+_Logo_Primary_WithoutStrapline_RGB_White_Yellow_Grad_EN.png";

const OFFERS_EN = [
  {
    number: "-- 01",
    title: "Customer Experience",
    description:
      "Design and orchestration of differentiated customer experiences, with a clear focus on customer value, loyalty, and measurable service improvement.",
  },
  {
    number: "-- 02",
    title: "Marketing Transformation",
    description:
      "Marketing capability transformation through data-driven, omnichannel, performance-led growth and stronger commercial activation.",
  },
  {
    number: "-- 03",
    title: "Product & Service Innovation",
    description:
      "From ideation to launch, shaping products and services that are desirable, viable, and ready to scale.",
  },
];

const OFFERS_FR = [
  {
    number: "-- 01",
    title: "Expérience Client",
    description:
      "Conception et orchestration d'expériences client différenciées, avec un accent clair sur la valeur client, la fidélité et l'amélioration mesurable du service.",
  },
  {
    number: "-- 02",
    title: "Transformation Marketing",
    description:
      "Transformation des capacités marketing grâce à une croissance axée sur les données, omnicanale et axée sur la performance, et à une activation commerciale plus forte.",
  },
  {
    number: "-- 03",
    title: "Innovation Produits & Services",
    description:
      "De l'idéation au lancement, façonner des produits et services qui sont désirables, viables et prêts à passer à l'échelle.",
  },
];

type Props = {
  assessmentId: number;
  language?: string | null;
};

export default function ReportGoFurtherSection({ assessmentId, language }: Props) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [clientName, setClientName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isFrench = (language ?? "").toLowerCase().startsWith("fr");
  const copy = reportCopy(isFrench);

  const openModal = () => {
    setIsModalOpen(true);
    setError(null);
  };

  const closeModal = () => {
    if (isSubmitting) return;
    setIsModalOpen(false);
    setClientName("");
    setError(null);
  };

  const handleBookConsultation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanedName = clientName.trim();
    if (!cleanedName) {
      setError(copy.nameRequired);
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/consultations/book`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assessment_id: assessmentId, client_name: cleanedName }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || (copy.gmailFailed));
      }
      const payload = (await response.json()) as { gmail_url?: string };
      if (!payload.gmail_url) {
        throw new Error(copy.gmailNoUrl);
      }
      window.open(payload.gmail_url, "_blank", "noopener,noreferrer");
      setIsModalOpen(false);
      setClientName("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : (copy.gmailFailed));
    } finally {
      setIsSubmitting(false);
    }
  };

  const offers = isFrench ? OFFERS_FR : OFFERS_EN;

  return (
    <section className="report-go-further-shell relative overflow-hidden px-3 py-4 text-white sm:px-6 sm:py-6 lg:px-10 lg:py-8 print:px-0 print:py-0">
      <div className="section">
        <div className="orbital-ring" />
        <div className="orbital-ring-small" />
        <div className="orbital-ring-left" />

        <div className="section-head">
          <span className="section-number">06</span>
          <h2 className="section-title">{copy.goFurther}</h2>
        </div>

        <div className="studio-wrap">
          <div className="studio-orbit-msg">
            <div className="som-av" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="3" fill="#ffd447" />
                <circle cx="12" cy="12" r="7" stroke="#ffd447" strokeWidth="1" strokeDasharray="2 2" opacity=".5" />
              </svg>
            </div>
            <div>
              <div className="som-from">{copy.closingKicker}</div>
              <div className="som-text">
                {copy.closingLead}
              </div>
            </div>
          </div>

          <div className="studio-card" id="contact">
            <div className="studio-top-bar" />
            <div className="studio-inner">
              <div className="studio-bg-glow" aria-hidden="true" />

              <h2 className="studio-hl">
                {isFrench ? (
                  <>
                    Certains écarts se comblent avec un document.
                    <br />
                    D'autres nécessitent <em>les bonnes personnes</em>
                    <br />
                    autour de la table.
                  </>
                ) : (
                  <>
                    Some gaps close with a document.
                    <br />
                    Others need <em>the right people</em>
                    <br />
                    in the room.
                  </>
                )}
              </h2>

              <div className="studio-body">
                {copy.closingBody}
              </div>

              <div className="studio-offers">
                {offers.map((offer) => (
                  <div className="s-offer" key={offer.number}>
                    <div className="so-accent" aria-hidden="true" />
                    <div className="so-num">{offer.number}</div>
                    <div className="so-t">{offer.title}</div>
                    <div className="so-d">{offer.description}</div>
                  </div>
                ))}
              </div>

              <div className="studio-cta-block">
                <div className="scta-text">
                  <div className="scta-label">{copy.bookingTitle}</div>
                  <h3 className="scta-heading">
                    {copy.bookingLead}
                  </h3>
                  <div className="scta-sub">
                    {copy.bookingReassurance}
                  </div>
                </div>
                <div className="scta-actions">
                  <button type="button" className="btn-primary" onClick={openModal}>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <path
                        d="M2 4l6 5 6-5"
                        stroke="#111318"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <rect x="1" y="3" width="14" height="10" rx="2" stroke="#111318" strokeWidth="1.5" />
                    </svg>
                    {copy.bookConsultation}
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => window.print()}>
                    {copy.downloadPdf}
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                      <path
                        d="M2 7h10M8 3l4 4-4 4"
                        stroke="currentColor"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <footer className="section-footer">
            <img src={STUDIO_LOGO_SRC} alt="EY Studio+ logo" />
            <p>
              {copy.copyright}
            </p>
          </footer>
        </div>
      </div>
      {isModalOpen ? (
        <div className="consultation-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="consultation-title">
          <form className="consultation-modal" onSubmit={handleBookConsultation}>
            <h3 id="consultation-title">
              {copy.bookingModalTitle}
            </h3>
            <p>
              {copy.bookingModalLead}
            </p>
            <div className="consultation-field">
              <label htmlFor="consultation-client-name">{copy.yourNameLabel}</label>
              <input
                id="consultation-client-name"
                type="text"
                value={clientName}
                onChange={(event) => setClientName(event.target.value)}
                placeholder="Ahmed Ben Ali"
                disabled={isSubmitting}
                autoFocus
              />
            </div>
            {error ? <div className="consultation-error">{error}</div> : null}
            <div className="consultation-modal-actions">
              <button type="button" className="btn-secondary" onClick={closeModal} disabled={isSubmitting}>
                {copy.cancel}
              </button>
              <button type="submit" className="btn-primary" disabled={isSubmitting || !clientName.trim()}>
                {isSubmitting
                  ? (copy.preparing)
                  : (copy.openGmail)}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </section>
  );
}
