/**
 * What an interview guide is, and the pure operations on one. No React, no network.
 *
 * A guide is five sections of questions. They are a literal union rather than something loaded
 * at runtime because they mirror the maturity framework's three axes, with a warm-up and a close
 * around them, and that shape does not vary per interview.
 */

export type AssessmentItem = {
  id: number;
  company_name: string;
  sector: string;
  size: string;
  region?: string | null;
  status: string;
  language?: string | null;
  created_at?: string;
  overall_maturity_band?: string | null;
};

export type InterviewGuideQuestionItem = {
  id: string;
  question: string;
  rationale: string;
  follow_up: string;
  isAnswered?: boolean;
  answerNote?: string;
};

export type SectionKey = "introduction" | "manage" | "analyze" | "improve" | "closure";

/** The five sections in the order a real interview runs through them. */
export const SECTION_KEYS: readonly SectionKey[] = [
  "introduction",
  "manage",
  "analyze",
  "improve",
  "closure",
];

/** The field on a guide that holds one section's questions, e.g. `"manage_questions"`. */
export type SectionQuestionsField = `${SectionKey}_questions`;

export type InterviewGuide = {
  id?: number;
  assessment_id: number | null;
  company_name: string;
  language: string;
  profile?: string;
  executive_summary: string;
  unanswered_areas: string[];
} & Record<SectionQuestionsField, InterviewGuideQuestionItem[]>;

/**
 * Which field holds a section's questions.
 *
 * The hub reads and writes sections by key, and building the field name inline meant an
 * `as keyof InterviewGuide` cast at every call site -- a cast that would have gone on compiling if
 * a section were ever renamed. The template-literal return type says the same thing without
 * lying, so a bad section key is now a compile error rather than an undefined array at runtime.
 */
export function questionsFieldFor(section: SectionKey): SectionQuestionsField {
  return `${section}_questions`;
}

/** A guide as it arrives from the API or from localStorage, before its shape can be trusted. */
export type RawInterviewGuide = Omit<Partial<InterviewGuide>, SectionQuestionsField> &
  Partial<Record<SectionQuestionsField, Partial<InterviewGuideQuestionItem>[]>>;

/**
 * Fill in what a stored or freshly generated guide may be missing.
 *
 * Two things make this necessary. The model returns questions without ids, and the UI edits,
 * deletes and reorders questions by id -- so ids are minted here, once, at the boundary. And a
 * guide saved by an older version of the app can be missing the answer-tracking fields entirely,
 * which would otherwise surface as `undefined` in the middle of a render.
 *
 * An id already present is always kept: regenerating them would detach a question from any answer
 * the consultant had already written against it.
 */
export function withQuestionIds(raw: RawInterviewGuide | null | undefined): InterviewGuide {
  // Callers pass straight from `JSON.parse` and from `res.json()`; a null here means the caller
  // has nothing to show, and it is handled downstream rather than turned into an empty guide.
  if (!raw) return raw as unknown as InterviewGuide;

  const withIds = (
    list: Partial<InterviewGuideQuestionItem>[] | undefined,
  ): InterviewGuideQuestionItem[] =>
    (list || []).map((q, idx) => ({
      ...q,
      id: q.id || `${Date.now()}-${Math.random()}-${idx}`,
      question: q.question || "",
      rationale: q.rationale || "",
      follow_up: q.follow_up || "",
      isAnswered: q.isAnswered !== undefined ? q.isAnswered : false,
      answerNote: q.answerNote || "",
    }));

  return {
    ...(raw as InterviewGuide),
    introduction_questions: withIds(raw.introduction_questions),
    manage_questions: withIds(raw.manage_questions),
    analyze_questions: withIds(raw.analyze_questions),
    improve_questions: withIds(raw.improve_questions),
    closure_questions: withIds(raw.closure_questions),
  };
}
