# Interview Guides — Module Reference

The Interview Guides module generates a tailored stakeholder interview script and provides two
LLM assistants on top of it. Its defining capability is **grounding**: a guide can be generated
from a prior maturity assessment, turning that assessment's scored capabilities and conversation
transcript into targeted interview questions.

- **Routes:** `backend/app/api/routes/assessments.py` (path prefix `/assessments/interview-guide/*`)
- **Generation & persistence:** `backend/app/services/assessment/reporting/reporting_service.py`
- **Chat assistant:** `backend/app/services/assessment/interview_chat.py`
- **Insights briefing:** `backend/app/services/assessment/interview_insights.py`
- **Chat store:** `backend/app/services/assessment/interview_chat_store.py`
- **Model:** `backend/app/db/models/interview_guide.py` · **Schema:** `backend/app/schemas/interview_guide.py`
- **Frontend:** `frontend/src/features/interview/hub.tsx`, `features/interview/history-table.tsx`

---

## 1. What it produces

One structured guide per row, shaped by the `InterviewGuideResponse` schema:

- `executive_summary` — the client's current status in prose.
- `unanswered_areas` — capabilities/areas that remain unclear.
- Five question sections mirroring the assessment axes:
  `introduction_questions`, `manage_questions`, `analyze_questions`, `improve_questions`,
  `closure_questions`.

Each question (`InterviewGuideQuestionItem`) carries:

| Field | Purpose |
|---|---|
| `question` | The open-ended question to ask |
| `rationale` | Why to ask it — typically tied to a specific assessment gap |
| `follow_up` | Deeper probes if the answer is thin (list is normalised to bulleted text) |
| `isAnswered` / `answerNote` | Filled in **live by the consultant** during the interview |

Schema validators coerce loose LLM output to strings and normalise `follow_up` lists into bulleted
text, so a slightly-off model response still validates.

---

## 2. Endpoints

All are consultant-only (the router applies `Depends(get_current_user)`).

| Method | Path | Purpose |
|---|---|---|
| POST | `/interview-guide/generate` | Generate a guide via LLM, grounded in an assessment when `assessment_id` is supplied |
| POST | `/interview-guide/save` | Insert or update; stamps `owner_id` on first save |
| GET | `/interview-guide/list` | History, scoped to visible-to-caller, with owner name + `question_count` + `has_insights` |
| GET | `/interview-guide/{id}` | Open one guide (IDOR-guarded; 404 for non-owners without share/project access) |
| DELETE | `/interview-guide/{id}` | Delete the guide + its chat history + project/share links (owner only) |
| POST | `/interview-guide/chat` | Ask the assistant about the current guide |
| GET | `/interview-guide/{id}/chat` | Restore persisted chat history on open |
| POST | `/interview-guide/insights` | Cross-reference interview vs. assessment; persist the briefing |

---

## 3. Data model

`interview_guides` table (`app/db/models/interview_guide.py`):

- `id`, `owner_id` (FK users), `assessment_id` (FK assessments, **`ON DELETE SET NULL`**).
- `company_name`, `profile`, `language`.
- `payload` **JSONB** — the entire guide (all five sections + answer notes) stored as one document.
- `insights` **JSONB** — the persisted cross-reference briefing `{markdown, generated_at,
  generated_by}`; null until the insights pass is run.
- `created_at`, `updated_at`.

**Design decisions:**
- **JSONB document, not shredded rows.** The guide is authored, edited, and saved as a unit, so a
  single JSONB column matching the schema fits better than a normalised `questions` table.
- **`SET NULL` on the assessment link.** Deleting the source assessment unlinks but does not delete
  the guide — the interview script outlives the diagnostic it came from.
- **Persisted insights.** The briefing is stored after first generation so history can display it
  without re-invoking the LLM (previously it was generated and discarded).

---

## 4. Generation flow (`get_interview_guide`)

1. **Load grounding (optional).** If `assessment_id` is set, fetch the assessment, its conversation
   **trace** (Orion Q&A), and its scored capabilities via
   `capabilities.list_all_for_assessment(...)`. Capabilities are split into two lists:
   - **Assessed** — `"[AXIS] label — Level N. Evidence: rationale"`.
   - **Gaps** — capabilities not assessed (the material to probe in the interview).
2. **Resolve parameters.** Request values (`company_name`, `sector`, `size`, `region`, `profile`,
   `language`, `custom_context`, `custom_profile_description`) override, falling back to the linked
   assessment's company details.
3. **Build the prompt.** System prompt from `build_interview_guide_prompt(profile, language,
   custom_profile_description)` + a language directive. User content concatenates the company
   profile, assessed capabilities, gaps, and the Orion transcript (or an explicit "generate from
   scratch" instruction when there is no history).
4. **Call the LLM with fallback.** Primary provider is Moonshot/Kimi (`_call_moonshot`); on any
   exception it falls back to the default Mistral gateway (`llm.gateway.chat_messages`). A provider
   outage degrades quality, not availability.
5. **Tolerant JSON parse.** `extract_json` extracts the JSON; `parse_q_items` maps field-name
   variants (`question`/`question_text`, `rationale`/`reason`/`why`, `follow_up`/`followup`) into
   `InterviewGuideQuestionItem`s. Unrecoverable output → HTTP **502** with a localized message.

The grounding step is the module's core value: unassessed/low capabilities become the questions to
ask, and each question's `follow_up` points back at the specific gap.

---

## 5. Save & history semantics (`save_interview_guide`)

- **Upsert by explicit `id` only.** A guide without an `id` always inserts a **new** row. (Previously
  it matched by `(company_name, profile)`, which silently overwrote a prior interview for the same
  company+profile and lost history.) This lets one company hold multiple distinct interviews.
- **Ownership on first save.** The route stamps `owner_id = user.id` only where it is currently null
  (`.where(InterviewGuide.owner_id.is_(None))`), so a shared guide re-saved by a collaborator never
  changes hands.
- **Scoped listing.** `/list` returns guides the caller owns or that are shared with them, joins the
  creator's `full_name`, and computes `question_count` and `has_insights` for the history table.

---

## 6. Chat assistant (`interview_chat.py`)

Interactive Q&A about the guide, built on the **shared RAG engine** (`app/services/rag/engine.py`,
`agentic_answer`).

- **Freshness first.** The consultant edits questions and records answers live. The guide is
  reloaded from the DB by `guide_id` (the autosaved source of truth), falling back to the copy sent
  in the request body for a brand-new unsaved guide. The assistant therefore always reasons over the
  guide exactly as it stands now.
- **Context injection.** `guide_to_context` serialises every section, each question's status, and
  the consultant's answer notes. The prior Orion self-assessment transcript is injected **only when
  the question calls for cross-referencing** — detected by EN/FR keyword triggers (`_ORION_TRIGGERS`:
  "earlier", "claimed", "consistent", "incohérent", …) — to keep ordinary questions token-lean.
- **System prompt** positions the model as a senior CX consultant; it must ground everything in the
  guide, never invent a client response, cite `[Interview Guide]`, and answer concisely.
- **Persistence.** Each turn is appended to the guide's chat history (`interview_chat_store`) and
  restored on reopen.

---

## 7. Insights briefing (`interview_insights.py`)

A single, non-interactive cross-reference pass, distinct from the chat.

- **Two sources:** (1) the Orion self-assessment transcript — what the client *claimed*; (2) the
  interview `answerNote`s — what the consultant *recorded*.
- **Output:** a short markdown briefing with three sections — **Key insights**, **Inconsistencies**
  (or exactly "No clear inconsistencies"), **Worth probing**. The prompt forbids fabricating an
  inconsistency.
- **Guard:** only meaningful when the guide was generated from an assessment that has a conversation;
  otherwise returns a status (`no_assessment` / `no_history`) rather than a hallucinated comparison.
- **Persisted** onto `interview_guides.insights` with `generated_at` and `generated_by`.

**Chat vs. insights:** the chat is interactive, guide-first, and pulls in the assessment only on
demand; insights is one-shot, comparison-first, always uses both sources, and saves its result.

---

## 8. Key technical decisions (summary)

- Whole guide stored as a **JSONB payload**; briefing as a second **JSONB** column.
- Assessment link is **`ON DELETE SET NULL`** — guides outlive their source assessment.
- **Multi-provider LLM** with automatic fallback (Moonshot → Mistral).
- **Tolerant JSON parsing** absorbs LLM field-name drift; unrecoverable output yields a clean 502.
- **Conditional context injection** (Orion triggers) trades a little precision for lower token cost.
- `repair_encoding` is applied to all LLM output to fix CP1252 mojibake.
- **IDOR guards + visibility scoping** on every read; **idempotent upsert-by-id** prevents history loss.
- Ownership set server-side only (no mass assignment). See
  [auth-projects-and-sharing.md](auth-projects-and-sharing.md) for the shared access model.
