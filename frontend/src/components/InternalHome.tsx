import { Fragment } from "react";
import { BRAND } from "../lib/brand";
import { pickCopy } from "../lib/i18n";
import FadeUp from "./FadeUp";
import {
  Gauge,
  MessagesSquare,
  Radio,
  FileSearch,
  ListChecks,
  FolderKanban,
  Users,
  Link2,
  ArrowRight,
  ChevronRight,
  Sparkles,
  Zap,
} from "lucide-react";

type Props = {
  /** Opens the services hub, the platform's primary entry point. */
  onOpenServices?: () => void;
  language?: string;
};

/* ------------------------------------------------------------------ copy --- */

const T = {
  en: {
    eyebrow: "EY CX Studio · Internal platform",
    heading: "One workspace for the whole CX engagement.",
    sub: "CX Studio brings every analysis tool and every client touchpoint into a single, project-centric workspace. The modules do the heavy lifting with AI, so findings flow from diagnostic to synthesis without leaving the platform.",
    primaryCta: "Open the Studio",
    secondaryCta: "See what's inside",
    capabilities: {
      eyebrow: "What's inside",
      heading: "Five modules, one pipeline.",
      sub: "Run them in sequence for a full engagement, or jump straight to the tool you need.",
      modules: [
        {
          icon: Gauge,
          tint: BRAND.gold,
          title: "Maturity Assessment",
          desc: "Score CX maturity across Manage, Analyze and Improve, as a guided chat or a link the client completes themselves.",
        },
        {
          icon: MessagesSquare,
          tint: BRAND.blue,
          title: "Interview Guide",
          desc: "Generate a tailored interview guide for any stakeholder, with saved history and AI insights on the answers.",
        },
        {
          icon: Radio,
          tint: "#10b981",
          title: "Social Listening",
          desc: "Pull public reviews and posts, then get AI-classified sentiment, themes and recurring complaints.",
        },
        {
          icon: FileSearch,
          tint: "#6366f1",
          title: "Desk Research",
          desc: "Upload client documents and get a structured synthesis with citations you can trust and reuse.",
        },
        {
          icon: ListChecks,
          tint: "#e11d48",
          title: "Issue Log",
          desc: "Consolidates every module's findings into one prioritized issue log, scored by severity and frequency, exportable to Excel.",
        },
      ],
    },
    roadmap: {
      eyebrow: "How you work",
      heading: "A pipeline you can follow, or dip into.",
      sub: "The five modules form a natural lifecycle. Use any of them on their own, or run them inside a project so the results build on each other.",
      freely: {
        title: "Use any tool on its own",
        desc: "Jump straight into a module and get a result. No setup, nothing else required.",
      },
      project: {
        title: "Or work inside a project",
        desc: "Create a project and each tool's output attaches to it and advances the pipeline, so every result builds on the last.",
        tag: "Recommended",
      },
    },
    ties: {
      eyebrow: "The platform",
      heading: "What ties it all together.",
      items: [
        { icon: FolderKanban, title: "Projects", desc: "A project is the anchor: it owns the results, tracks the pipeline steps, and shows what's done and what's next." },
        { icon: Users, title: "Collaboration", desc: "Add colleagues as members, or share a single analysis. Access is scoped, so people see only their work and what's shared with them." },
        { icon: Link2, title: "Client links", desc: "Send a maturity assessment as a passwordless link. The client fills it in, and the result lands straight on your dashboard." },
      ],
    },
    useCases: {
      eyebrow: "Use cases",
      heading: "What a typical engagement looks like.",
      items: [
        {
          step: "01",
          title: "Kick off with a diagnostic",
          desc: "Start a maturity assessment yourself, or send the client a link. Either way the scored result is saved to the project and ready to build on.",
        },
        {
          step: "02",
          title: "Go deep with stakeholders",
          desc: "Generate interview guides tailored to each role, run the conversations, and let the AI surface the insights hiding in the answers.",
        },
        {
          step: "03",
          title: "Bring in the outside view",
          desc: "Add social listening and desk research to the same project, so market signal and client documents sit next to your primary findings.",
        },
        {
          step: "04",
          title: "Synthesize and share",
          desc: "Everything is already in one place: hand the project to a colleague, or export the pieces you need for the deck.",
        },
      ],
    },
    finalCta: {
      heading: "Ready when you are.",
      sub: "Open the Studio and pick up a project, or start a new one.",
      button: "Open the Studio",
    },
  },
  fr: {
    eyebrow: "EY CX Studio · Plateforme interne",
    heading: "Un seul espace pour toute la mission CX.",
    sub: "CX Studio réunit chaque outil d'analyse et chaque point de contact client dans un espace unique, centré sur le projet. Les modules font le gros du travail avec l'IA, pour que les constats circulent du diagnostic à la synthèse sans quitter la plateforme.",
    primaryCta: "Ouvrir le Studio",
    secondaryCta: "Voir le contenu",
    capabilities: {
      eyebrow: "Le contenu",
      heading: "Cinq modules, un seul pipeline.",
      sub: "Enchaînez-les pour une mission complète, ou allez directement à l'outil dont vous avez besoin.",
      modules: [
        {
          icon: Gauge,
          tint: BRAND.gold,
          title: "Diagnostic de maturité",
          desc: "Évaluez la maturité CX sur les axes Piloter, Analyser et Améliorer, en chat guidé ou via un lien que le client remplit lui-même.",
        },
        {
          icon: MessagesSquare,
          tint: BRAND.blue,
          title: "Guide d'entretien",
          desc: "Générez un guide d'entretien sur mesure pour chaque interlocuteur, avec historique et analyses IA des réponses.",
        },
        {
          icon: Radio,
          tint: "#10b981",
          title: "Écoute sociale",
          desc: "Récupérez avis et publications, puis obtenez sentiment, thèmes et plaintes récurrentes classés par IA.",
        },
        {
          icon: FileSearch,
          tint: "#6366f1",
          title: "Desk Research",
          desc: "Importez les documents client et obtenez une synthèse structurée, avec des citations fiables et réutilisables.",
        },
        {
          icon: ListChecks,
          tint: "#e11d48",
          title: "Registre des enjeux",
          desc: "Consolide les constats de chaque module en un registre priorisé, noté par gravité et fréquence, exportable vers Excel.",
        },
      ],
    },
    roadmap: {
      eyebrow: "Comment travailler",
      heading: "Un pipeline à suivre, ou à piocher.",
      sub: "Les cinq modules forment un cycle naturel. Utilisez-les seuls, ou lancez-les dans un projet pour que les résultats s'enchaînent.",
      freely: {
        title: "Utiliser un outil seul",
        desc: "Lancez directement un module et obtenez un résultat. Aucune configuration requise.",
      },
      project: {
        title: "Ou travailler dans un projet",
        desc: "Créez un projet : chaque résultat s'y rattache et fait avancer le pipeline, pour que chaque analyse s'appuie sur la précédente.",
        tag: "Recommandé",
      },
    },
    ties: {
      eyebrow: "La plateforme",
      heading: "Ce qui relie le tout.",
      items: [
        { icon: FolderKanban, title: "Projets", desc: "Le projet est l'ancre : il détient les résultats, suit les étapes du pipeline et montre ce qui est fait et ce qui reste." },
        { icon: Users, title: "Collaboration", desc: "Ajoutez des collègues comme membres, ou partagez une seule analyse. L'accès est cadré, chacun voit son travail et ce qui lui est partagé." },
        { icon: Link2, title: "Liens client", desc: "Envoyez un diagnostic de maturité sous forme de lien sans mot de passe. Le client le remplit, le résultat arrive sur votre tableau de bord." },
      ],
    },
    useCases: {
      eyebrow: "Cas d'usage",
      heading: "À quoi ressemble une mission type.",
      items: [
        {
          step: "01",
          title: "Démarrer par un diagnostic",
          desc: "Lancez un diagnostic vous-même, ou envoyez un lien au client. Dans les deux cas, le résultat scoré est sauvegardé dans le projet.",
        },
        {
          step: "02",
          title: "Approfondir avec les parties prenantes",
          desc: "Générez des guides d'entretien adaptés à chaque rôle, menez les échanges, et laissez l'IA révéler les insights cachés dans les réponses.",
        },
        {
          step: "03",
          title: "Apporter le regard externe",
          desc: "Ajoutez écoute sociale et desk research au même projet : le signal marché et les documents client côtoient vos constats.",
        },
        {
          step: "04",
          title: "Synthétiser et partager",
          desc: "Tout est déjà réuni : confiez le projet à un collègue, ou exportez les éléments dont vous avez besoin pour le livrable.",
        },
      ],
    },
    finalCta: {
      heading: "Prêt quand vous l'êtes.",
      sub: "Ouvrez le Studio et reprenez un projet, ou lancez-en un nouveau.",
      button: "Ouvrir le Studio",
    },
  },
};

/* --------------------------------------------------------------- helpers --- */

function hexToRgba(hex: string, alpha: number) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

/* ------------------------------------------------------------- component --- */

export default function InternalHome({ onOpenServices, language = "en" }: Props) {
  const t = pickCopy(T, language);

  return (
    <div className="bg-[linear-gradient(180deg,#ffffff_0%,#fbfcfd_45%,#f7f9fb_100%)] text-ink">
      {/* ─── Objective / hero ─────────────────────────────────────────── */}
      <section id="start" className="relative overflow-hidden py-20 sm:py-24 lg:py-28">
        <div className="pointer-events-none absolute right-[-8%] top-[4%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(197,160,79,0.10),rgba(255,255,255,0))] blur-3xl" />
        <div className="pointer-events-none absolute left-[-10%] bottom-[2%] h-[26rem] w-[26rem] rounded-full bg-[radial-gradient(circle,rgba(56,88,233,0.08),rgba(255,255,255,0))] blur-3xl" />
        <div className="relative mx-auto max-w-5xl px-6 text-center lg:px-12">
          <FadeUp>
            <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 shadow-sm backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-ey-gold" />
              {t.eyebrow}
            </span>
          </FadeUp>
          <FadeUp delay="delay-1">
            <h1 className="mx-auto mt-7 max-w-3xl text-4xl font-medium leading-[1.06] tracking-[-0.04em] sm:text-5xl md:text-6xl">
              {t.heading}
            </h1>
          </FadeUp>
          <FadeUp delay="delay-2">
            <p className="mx-auto mt-6 max-w-2xl text-lg font-light leading-8 text-[#374151]">
              {t.sub}
            </p>
          </FadeUp>
          <FadeUp delay="delay-3">
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={onOpenServices}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-8 py-3.5 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:bg-ink-hover"
              >
                {t.primaryCta}
                <ArrowRight className="h-4 w-4" />
              </button>
              <a
                href="#capabilities"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-slate-300 bg-white px-7 py-3.5 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
              >
                {t.secondaryCta}
              </a>
            </div>
          </FadeUp>
        </div>
      </section>

      {/* ─── Capabilities: the five modules ───────────────────────────── */}
      <section id="capabilities" className="border-t border-slate-100 bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <FadeUp>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-ey-gold">{t.capabilities.eyebrow}</p>
            <h2 className="mt-3 text-3xl font-medium tracking-[-0.03em] sm:text-4xl">{t.capabilities.heading}</h2>
            <p className="mt-3 max-w-2xl text-base leading-7 text-slate-500">{t.capabilities.sub}</p>
          </FadeUp>

          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {t.capabilities.modules.map((m, i, all) => (
              <FadeUp
                key={m.title}
                delay={`delay-${(i % 2) + 1}`}
                /* An odd module count would leave a gap in the last row. The Issue Log is the one
                   that consolidates the other four, so it earns the full-width slot at the foot. */
                className={i === all.length - 1 && all.length % 2 === 1 ? "md:col-span-2" : ""}
              >
                <div className="group flex h-full gap-5 rounded-3xl border border-slate-100 bg-[#fbfcfd] p-7 transition hover:-translate-y-1 hover:border-slate-200 hover:shadow-[0_20px_40px_rgba(17,24,39,0.08)]">
                  <span
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"
                    style={{ backgroundColor: hexToRgba(m.tint, 0.12), color: m.tint }}
                  >
                    <m.icon className="h-6 w-6" />
                  </span>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">{m.title}</h3>
                    <p className="mt-1.5 text-sm leading-7 text-slate-500">{m.desc}</p>
                  </div>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Roadmap: the pipeline + two ways to work ─────────────────── */}
      <section id="roadmap" className="border-t border-slate-100 py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <FadeUp>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-ey-gold">{t.roadmap.eyebrow}</p>
            <h2 className="mt-3 text-3xl font-medium tracking-[-0.03em] sm:text-4xl">{t.roadmap.heading}</h2>
            <p className="mt-3 max-w-2xl text-base leading-7 text-slate-500">{t.roadmap.sub}</p>
          </FadeUp>

          {/* Pipeline drawing */}
          <FadeUp delay="delay-1">
            <div className="mt-12 overflow-x-auto pb-2">
              <div className="flex min-w-max items-stretch gap-2 sm:gap-3">
                {t.capabilities.modules.map((m, i, all) => (
                  <Fragment key={m.title}>
                    <div className="flex w-40 flex-col items-center rounded-2xl border border-slate-100 bg-white px-4 py-5 text-center shadow-[0_8px_20px_rgba(17,24,39,0.04)]">
                      <span
                        className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold"
                        style={{ backgroundColor: hexToRgba(m.tint, 0.12), color: m.tint }}
                      >
                        {i + 1}
                      </span>
                      <span className="mt-3" style={{ color: m.tint }}>
                        <m.icon className="h-5 w-5" />
                      </span>
                      <p className="mt-2 text-sm font-semibold leading-5 text-slate-800">{m.title}</p>
                    </div>
                    {/* the chevron is a link between two nodes, so the last node has none */}
                    {i < all.length - 1 && (
                      <div className="flex items-center">
                        <ChevronRight className="h-5 w-5 text-slate-300" />
                      </div>
                    )}
                  </Fragment>
                ))}
              </div>
            </div>
          </FadeUp>

          {/* Two ways to work */}
          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <FadeUp delay="delay-1">
              <div className="flex h-full gap-5 rounded-3xl border border-slate-100 bg-white p-7 shadow-[0_8px_20px_rgba(17,24,39,0.04)]">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
                  <Zap className="h-6 w-6" />
                </span>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">{t.roadmap.freely.title}</h3>
                  <p className="mt-1.5 text-sm leading-7 text-slate-500">{t.roadmap.freely.desc}</p>
                </div>
              </div>
            </FadeUp>
            <FadeUp delay="delay-2">
              <div className="relative flex h-full gap-5 rounded-3xl border border-slate-900/10 bg-[#0b0f1a] p-7 shadow-[0_20px_40px_rgba(11,15,26,0.18)]">
                <span className="absolute right-5 top-5 rounded-full bg-ey-gold/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#d8b678]">
                  {t.roadmap.project.tag}
                </span>
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/10 text-white">
                  <FolderKanban className="h-6 w-6" />
                </span>
                <div>
                  <h3 className="text-lg font-semibold text-white">{t.roadmap.project.title}</h3>
                  <p className="mt-1.5 text-sm leading-7 text-slate-300">{t.roadmap.project.desc}</p>
                </div>
              </div>
            </FadeUp>
          </div>
        </div>
      </section>

      {/* ─── Platform: what ties it together ──────────────────────────── */}
      <section id="platform" className="border-t border-slate-100 bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <FadeUp>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-ey-gold">{t.ties.eyebrow}</p>
            <h2 className="mt-3 text-3xl font-medium tracking-[-0.03em] sm:text-4xl">{t.ties.heading}</h2>
          </FadeUp>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {t.ties.items.map((it, i) => (
              <FadeUp key={it.title} delay={`delay-${i + 1}`}>
                <div className="h-full rounded-3xl border border-slate-100 bg-[#fbfcfd] p-7 shadow-[0_8px_20px_rgba(17,24,39,0.04)]">
                  <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white">
                    <it.icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold text-slate-900">{it.title}</h3>
                  <p className="mt-2 text-sm leading-7 text-slate-500">{it.desc}</p>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Use cases ────────────────────────────────────────────────── */}
      <section id="use-cases" className="border-t border-slate-100 py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <FadeUp>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-ey-gold">{t.useCases.eyebrow}</p>
            <h2 className="mt-3 text-3xl font-medium tracking-[-0.03em] sm:text-4xl">{t.useCases.heading}</h2>
          </FadeUp>
          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {t.useCases.items.map((it, i) => (
              <FadeUp key={it.step} delay={`delay-${(i % 2) + 1}`}>
                <div className="flex h-full gap-5 rounded-3xl border border-slate-100 bg-[#fbfcfd] p-7 shadow-[0_8px_20px_rgba(17,24,39,0.04)]">
                  <div className="text-2xl font-semibold tabular-nums text-slate-200">{it.step}</div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">{it.title}</h3>
                    <p className="mt-1.5 text-sm leading-7 text-slate-500">{it.desc}</p>
                  </div>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Final CTA ────────────────────────────────────────────────── */}
      <section className="px-6 pb-24 pt-20 lg:px-12">
        <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-[#0b0f1a] px-8 py-16 text-center shadow-[0_30px_60px_rgba(11,15,26,0.35)] sm:px-16">
          <div className="pointer-events-none absolute right-[-6%] top-[-30%] h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(197,160,79,0.22),rgba(11,15,26,0))] blur-2xl" />
          <div className="pointer-events-none absolute left-[-6%] bottom-[-30%] h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(56,88,233,0.20),rgba(11,15,26,0))] blur-2xl" />
          <div className="relative">
            <h2 className="text-3xl font-medium tracking-[-0.03em] text-white sm:text-4xl">{t.finalCta.heading}</h2>
            <p className="mx-auto mt-4 max-w-lg text-base leading-7 text-slate-300">{t.finalCta.sub}</p>
            <button
              type="button"
              onClick={onOpenServices}
              className="mt-9 inline-flex items-center justify-center gap-2 rounded-full bg-white px-8 py-3.5 text-sm font-semibold text-[#0b0f1a] shadow-lg transition hover:-translate-y-0.5 hover:bg-slate-100"
            >
              {t.finalCta.button}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
