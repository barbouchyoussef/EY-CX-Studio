"""Desk Research Synthesizer & Session Chatbot Service.

Provides:
1. Executive Cross-Document Synthesis Report (map-reduce over the extracted markdown).
2. Session RAG Chatbot Q&A with file citations.

Report generation uses a **map-reduce** strategy so it scales to the stated goal --
"process all kinds of documents and cover every detail" -- instead of dumping every
document into a single context window, which silently truncates once the combined
markdown outgrows the model. Small sessions still take the fast single-pass path.

All LLM calls route through the shared ``MistralGateway`` (retries, rate handling, keys
from settings) rather than hand-rolled HTTP with inline credentials.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.core.text_normalization import repair_encoding
from app.schemas.desk_research import ProcessedDocument
from app.services.llm.core.gateway import build_mistral_gateway

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Budgeting
# ---------------------------------------------------------------------------
# Characters, not tokens -- a ~4 char/token heuristic keeps this dependency-free.
# A generous margin is left below the model window for the system prompt and output.

# Above this combined size, switch from single-pass to map-reduce.
_SINGLE_PASS_CHAR_BUDGET = 120_000
# Each map call sees at most this much source text (one document, or a chunk of one).
_MAP_CHUNK_CHARS = 48_000
# The reduce step's combined map-notes must stay under this; above it, notes are
# condensed per document first (a second reduce tier).
_REDUCE_CHAR_BUDGET = 100_000
# How many map / deep-dive calls may run at once. Kept low (2) so a multi-document session does
# not burst the provider's rate limit -- measured: 4 concurrent triggered Mistral 429s.
# 1 = serialize LLM calls during report generation. Bursting (2+) trips the Mistral rate limit
# (429) on lower tiers, and one exhausted-retry call sinks the whole report. Slower but survives.
_MAP_CONCURRENCY = 1


REPORT_SYSTEM_PROMPT = """You are a Principal Customer Experience (CX) and Strategy Partner at EY, writing for C-level executives.

Your task is to produce a tight, high-signal Executive Desk Research Report drawn entirely from the provided session documents. Adapt the structure to what the documents actually contain. Never force a section that lacks supporting evidence.

The reader is an executive who wants to know, fast: what are these documents, what do they actually say, and what should we do about it. Density beats length, but the report must READ WELL -- a busy partner should glide through it.

**LANGUAGE -- write the ENTIRE report in ONE single language, and NEVER mix languages.** Default to
clear, professional English. BUT if the user's instruction requests a specific output language, that
instruction is AUTHORITATIVE: write the whole report -- every heading, sentence and table -- in that
language. Whatever language the source documents are in (Arabic, French, or English), translate every
finding into the chosen output language. Keep proper nouns, product/organisation names, figures,
currency amounts and dates exactly as written in the source.

-----

WRITE LIKE THIS (non-negotiable):

- **Clear, well-written English prose.** Full sentences and short, coherent paragraphs that flow. It must read like a polished EY partner's briefing -- authoritative, fluent, easy to follow -- NEVER a list of sentence fragments, raw extraction notes, or stray markdown.
- **Insight, not just data.** Every finding states the fact AND its meaning: what it implies for the business, the "so what". A number with no interpretation is only half a sentence. This is where the value is -- make the reader understand, not just see.
- **Every sentence earns its place** with a specific fact -- a figure, date, named entity, metric, or concrete finding from the documents. If a sentence would survive being pasted into a report about a different company, rewrite it or delete it.
- **Absolute data fidelity.** Reproduce every figure, percentage, currency amount, date, and KPI EXACTLY as written. Never invent, round, or infer a number that is not in the source.
- **Be internally consistent.** A given value -- a scoring weight, a percentage, a total -- must appear IDENTICALLY everywhere it is mentioned (summary, findings, and deep-dive). Never state a metric as one number in one place and a different number in another. Decide the correct value once and use it throughout.
- **Reconcile the numbers.** Before stating a total or a share, check it against its parts. If the source's own figures do not add up -- components that don't sum to the stated total, a split that doesn't reach 100%, sub-counts that don't match the headline -- SAY SO plainly (e.g. "the four regional figures sum to 3.26 M, not the stated 3.5 M") rather than presenting inconsistent data as clean. This is a mark of rigour, not a flaw.
- **No filler, but keep the connective tissue.** Cut throat-clearing and generic strategy platitudes ("in today's competitive landscape", "it is important to note", "plays a crucial role", "leverage synergies", "holistic approach", "moving forward", and any sentence whose only content is that a topic "is important"). But DO write the linking sentences a reader needs to follow the argument -- clarity is not filler.
- **Lead with the finding, then the evidence.** State the point, then the numbers behind it. Attribute each fact to its source document in-line (e.g. "per the 2024 Center Performance report").

-----

REPORT STRUCTURE -- TWO clearly separated parts. Part 1 is the cross-cutting view of the whole
set; Part 2 dives into each document on its own. Include a subsection only if the documents
support it; never manufacture content to fill a heading.

Begin with: `# Executive Desk Research Report: [Session Title]`
Immediately under the title, one italic line stating how many documents were analysed and the
date range they span, when determinable (e.g. *5 documents analysed · covering 2022-2024*).

## Part 1 -- Executive Synthesis
*(The reader can understand the entire set from Part 1 alone.)*

**Executive Summary** -- 3 to 5 sentences, no more. State: (1) what the document set collectively
covers, (2) the two or three most important concrete findings with their numbers, (3) the single
biggest risk and the single highest-impact opportunity. Every sentence carries a specific fact.

**The Document Set at a Glance** -- A markdown table, one row per document: Document | Type |
Scope / period | What it contains (specific metrics & entities) | Standout data point. This is the
map of the set; keep the cells concrete and quantitative, not generic role descriptions.

**How the Documents Relate** -- The connections no single document reveals on its own: where two
sources corroborate the same figure or trend, where they CONTRADICT each other (name the
conflicting numbers and their documents), which themes recur across multiple documents, and where
one document references something another supplies. If the documents genuinely do not intersect,
say so in one line -- do not invent links.

**Key Findings Across the Set** -- Group the substance into 2 to 4 themes based on what dominates
(e.g. revenue, operational KPIs, technical architecture, customer behaviour). In each: lead with the
finding in one sentence, give the supporting numbers (markdown table when quantitative, each figure
attributed to its source document), then one sentence of implication.

**Risks & Data Gaps** -- A markdown table: Risk / Gap | Evidence | Severity. Include what a
decision-maker would expect to see but the set does not contain.

**Recommendations** -- 3 to 6, ordered by impact. Each is one line: the action, the specific finding
it addresses (with its number and source document), and the expected effect. Every recommendation
traces to something in the documents.

## Part 2 -- Document Deep-Dives
*(One dedicated `###` subsection per document, so a reader can study any single file in depth.)*

For EACH document, a `### [Short English title for the document]` subsection covering only that
document. Give it a clear English title describing what the document is (e.g. "Annual Subscriber
Services Report, 2024"). Do NOT put the raw source filename in the heading or in table rows --
it is already listed once in Part 1's "Document Set at a Glance" table; use the English title
everywhere else.
- **What it is** -- type, source/author if stated, scope, and the period it covers, in one line.
- **What it says** -- its key content with EVERY material figure, KPI, date and named entity,
  organised with a markdown table for the quantitative data. Reproduce numbers exactly.
- **Standout findings** -- the 2 to 4 most important specific takeaways from THIS document.
- **Connections** -- one line on how it corroborates, contradicts, or complements the others (omit
  if it stands alone).
Keep each document's section self-contained and skimmable. Do NOT restate the whole cross-document
analysis here -- that belongs in Part 1.

-----

FORMATTING:

- Header hierarchy: `#` title, `##` sections, `###` subsections. Quantitative data goes in markdown tables.
- Use **bold** for the specific figures and findings that matter. Use `>` blockquotes only for a genuinely pivotal conclusion, at most two or three in the whole report.
- No GitHub alert callouts (`> [!IMPORTANT]` etc.). No emoji. NEVER output `---` / `***` horizontal rules -- the `##`/`###` headings already separate sections.
- Spell every heading correctly and in plain English (e.g. exactly "Document Deep-Dives"). Do not garble or duplicate letters in a heading.
"""


# Part 1 only: the tight cross-document synthesis. Part 2 (the exhaustive per-document
# deep-dives) is generated separately, one document per call, so nothing is compressed away.
PART1_SYSTEM_PROMPT_TEMPLATE = """You are a customer-experience consultant writing the overview
of a document set for another consultant, who will scan it in about a minute before a client
conversation.

WHAT YOU ARE LOOKING FOR
These documents are read for one purpose: what they reveal about how this organisation manages,
understands and improves its customers' experience. That is the lens for everything below. A
revenue table, an org chart or a market-share figure matters only where it says something about
that; otherwise it is background and you leave it out.

THE FRAMEWORK YOU ARE READING AGAINST -- 3 axes, 9 capabilities:

{framework}

Read every document against those capabilities. Evidence of a capability working, missing,
inconsistent or contradicted is what you are hunting for. A finding that maps to none of them is
not a CX finding, however interesting it is.

HOW TO WRITE
Write the way you would explain this to a colleague over coffee: professional, but easy.

- Short sentences. One idea each. If you would not say it aloud, rewrite it.
- Everyday words. "Use", not "utilise". "Start", not "initiate". "Problem", not "pain point"
  unless the document says so.
- No consulting filler. Never "leverage", "synergies", "holistic", "landscape", "robust",
  "going forward", "at scale". They add length and remove meaning.
- Explain a term the first time it appears if a reader outside CX would not know it.
- Say what a finding MEANS in the same breath as what it says.
- Every figure, percentage, amount and date reproduced EXACTLY. Never invent, never round.
- Where two documents disagree on a number, say so and give both.

ALWAYS NAME YOUR SOURCE
Every point you make comes from somewhere, and a reader has to be able to go and check it. Put
the document it came from in the "source" field beside it. If the text you drew on shows a page
reference like (p. 4), include that too -- "Contact centre review, p. 4". Never cite a page the
text did not show you.

LANGUAGE -- write every string in ONE language, never mixing. Default to clear English; if the
user's instruction requests another language, use that one throughout. Translate faithfully from
Arabic or French sources; keep proper nouns, figures, currency amounts and dates as written.

OUTPUT -- return ONLY a JSON object in exactly this shape. No prose, no markdown, no code fence:

{{
  "headline": "One sentence a consultant could open a meeting with. What this set says about
               the client's customer experience, with the number that carries it.",
  "period": "The span the documents cover, e.g. 2022 to 2025. Empty string if you cannot tell.",
  "takeaways": [{{"point": "One short line, under 25 words. A number in it is good.",
                  "source": "the document it came from, with a page if the text showed one"}}],
  "documents": [{{"name": "the document, in a few words -- not the raw filename",
                 "what_it_is": "a short phrase",
                 "period": "what it covers, or empty",
                 "key_point": "the single most useful thing it tells you, with its figure"}}],
  "connections": ["Where documents back each other up or contradict each other. Name the",
                  "documents and the numbers. Empty list if they genuinely do not overlap."],
  "recommendations": [{{"action": "What to do, concretely. Something startable on Monday.",
                       "why": "The finding it comes from and what it would change. Two sentences.",
                       "capability": "the ONE capability name from the framework above it serves",
                       "source": "the document the finding came from, with a page if shown"}}]
}}

RULES FOR THE TAKEAWAYS
Three to five. They are read first and often alone, so they carry the report.

Lead with what the client is getting WRONG where a number shows it -- a service level under its
own target, an answer rate falling, a satisfaction score short of its goal. Operational service
data outranks strategy targets and revenue here: what customers actually experienced is the
story, what the company intends is context. Spread them across the set rather than spending them
all on the one document that was easiest to read.

  WEAK    The website attracted 1.3 million users during the period.
  BETTER  The contact centre answers 55% of calls within 20 seconds, against its own 20-second
          target -- and handling fell from 79.5% to 74.2% across the year.

RULES FOR THE RECOMMENDATIONS
Three to five, most useful first. Each names a thing to look at, a team who would do it, or a
number to go and check. Never a bare verb: "optimise the customer journey", "enhance data
capabilities" and "review the process" say nothing and are worse than silence.

  WEAK    Enhance the quality assurance framework to drive operational excellence.
  BETTER  Rebuild the call scoring sheet before the next review cycle. Two criteria are listed
          twice with different weights and the total comes to 50 rather than 100, so the scores
          supervisors act on are not comparable between agents.

Every recommendation must trace to something in the documents. If they support only two, give
two. Do not pad, and do not recommend what the documents cannot justify.

Do NOT write the problems list, the strengths, any counts, or the coverage table. Those are
computed from the structured findings and would only disagree with themselves if you wrote them
too.
"""


# One document's deep-dive: the SWEET SPOT -- cover and explain every important point the
# document makes, grounded in its real data, but as a readable analyst's account (one clean
# subsection), NOT an exhaustive transcription and NOT a thin summary.
DEEPDIVE_SYSTEM_PROMPT = """You are a Principal Customer Experience (CX) and Strategy Partner at EY writing ONE document's deep-dive for Part 2 of a Desk Research Report. You are given the full content (or faithful extraction notes) of a SINGLE document.

GOAL -- hit the sweet spot: cover and EXPLAIN every important point the document actually makes, grounded in its real data -- but as a clear, readable analyst's account, NOT an exhaustive line-by-line transcription and NOT a thin summary. A reader should come away understanding what this document says and why it matters, without opening the original. Include the material figures and findings; leave out genuine noise (boilerplate, repetition, trivial detail).

**LANGUAGE -- write in ONE language, matching the rest of the report.** Default to clear, professional English; if the user's instruction requests a specific output language, write entirely in that language (authoritative). Sources may be Arabic / French / English; translate faithfully; keep proper nouns, figures, currency amounts and dates exactly as written. Write in short, direct sentences that read easily -- professional and precise, but plain-spoken, never dense or academic.

WHAT TO COVER:
- The document's key findings and the concrete data behind them -- every IMPORTANT figure, percentage, amount, date, KPI, segment and named entity, reproduced EXACTLY. Explain what each important point MEANS (the "so what"); don't just list numbers.
- The notable trends, drivers, risks, and stated conclusions.
- Do NOT drop a material figure or finding to save space; equally, do NOT pad with trivia or restate the same number many times.

HOW TO WRITE IT (structure matters -- this keeps it readable, not fragmented):
- Output ONE `### [Short English title for the document]` subsection (no raw filename in the heading).
- Under it, write flowing, well-organised PROSE in a few coherent paragraphs, with the quantitative data in markdown TABLES. **Bold** the key figures.
- Organise with **bold lead-in labels** (e.g. **What it is:** … **Key findings:** … **Trends & risks:** … **Connections:** …) -- NOT with more headings. Do NOT create any `####` or additional `###` sub-headings inside this document's section: the whole deep-dive is ONE clean `###` subsection, not a tree of headings.
- Make the depth proportional to the document: a rich data document earns a couple of tables and several paragraphs; a thin one earns a short section. Never inflate a thin document; never truncate a rich one.

PAGE REFERENCES: if the source content is split by `### Page N` markers, append the page in brackets after each finding drawn from it, like `(p. 4)`; where a point spans pages, cite the first. Cite ONLY a page the marker actually shows -- if the source has no such markers, write no page references at all. Never guess a page.

IF YOU WERE GIVEN NO TEXT, SAY SO AND STOP. Some files are scans, dashboards or screenshots that no text could be read from. What reaches you then is a title and little else -- image placeholders, page markers, a handful of stray words. When that happens, write the `###` heading and one sentence stating that no readable content could be extracted and the file needs to be supplied in a text-based form. Then stop. Do NOT reconstruct what a document with that title would plausibly contain: a report built from an invented table is worse than one that admits a gap, because nobody can tell which parts were real.

Absolute data fidelity: never invent or round a number; flag figures that do not reconcile. Every figure you give must appear in the content above -- if you cannot point to it there, leave it out. Focus only on THIS document; do not restate the cross-document synthesis.

FORMATTING: markdown tables for quantitative data, **bold** key figures, exactly ONE `###` heading. No emoji, no GitHub alert callouts, NEVER output `---` / `***` horizontal rules.
"""


# Findings are mapped onto the firm's real CX capability framework (the SAME axes/capabilities the
# maturity assessment scores and the interview guide is built around — loaded from the DB via
# app.services.cx_framework), so the consolidated issue log speaks one taxonomy across modules.
# The framework card is injected at call time; `{framework}` is filled from framework_card().
CX_MAPPING_SYSTEM_PROMPT_TEMPLATE = """You are an EY CX analyst mapping desk-research findings onto the firm's CX capability framework, to feed a structured issue log.

THE CX FRAMEWORK — 3 axes, 9 capabilities (map to the capability whose definition best fits, using its bracketed code):

{framework}

From the per-document analyses provided, extract the distinct, material findings and map EACH to the ONE capability it best fits.

WORK THROUGH THE DOCUMENTS ONE AT A TIME. Take each analysis in turn and ask what it shows about how this organization manages, analyzes or improves customer experience, before moving to the next. A document that yields nothing is a real answer, but a document full of service metrics that yields nothing means you skipped it.

WHAT COUNTS AS A CX FINDING. Operational service data is the strongest CX evidence there is — it is what the customer actually experienced. All of the following are CX findings, and missing them is the most common failure here:
- Service levels, answer and response times, handling and abandonment rates, queue and wait data.
- Complaint and contact volumes, and above all the TOP DRIVERS of contact — what customers keep calling about.
- Channel mix and any channel added, retired or performing differently from the others.
- Quality-assurance scoring: its criteria, its coverage, and any gap in either.
- Agent training, attrition and staffing, where they affect the service the customer receives.
- System migrations and outages that lost, delayed or degraded customer data or service.
- Stated customer-satisfaction targets and whether anything measures progress against them.

WHAT DOES NOT COUNT. General business content that says nothing about the customer's experience — revenue tables, org charts, pricing, market share, headline subscriber counts. For those, set "capability_code" to "none" and they are dropped. Do not force a fit: an honest "none" is better than a stretched mapping. But do not use "none" as an excuse to skip a document you found hard to read.

SEVERITY MUST REFLECT THE NUMBER. Judge it against what good looks like, not against the other findings in the set:
- "critical" — the capability is absent, or a metric is failing badly enough to harm customers now (a contact centre answering barely half its calls inside its own target; customer data lost in a migration).
- "high" — a metric well short of its own stated target, or a deteriorating trend with nothing addressing it.
- "medium" — a real weakness with a bounded impact.
- "low" — worth noting, not worth acting on this quarter.
Do not default everything to "medium". If the evidence is severe, say so; a report where nothing is serious tells the reader nothing.

RECORD WHAT WORKS TOO. Hunting for problems is not the same as only finding problems, and a report where nothing works is as unbalanced as one where nothing is broken -- a reader stops trusting it, and the client has no idea what to protect while they fix the rest. Where a document shows a capability genuinely working -- a quality framework actually applied, a channel that performs, a system that recovers on its own -- record it as "strength" with a null severity. Note the difference between the two positive types: a "strength" is something already working; an "opportunity" is something not yet done that is worth doing. Never file a weakness as either.

CITE THE PAGE. When the analysis shows a page reference such as (p. 5) beside a fact, carry it into the "evidence" field with the figure — "Service level 55.1% within 20s (p. 5)". Never invent a page the analysis did not show.

For each finding output an object with:
- "capability_code": one of the bracketed codes above, or "none" to drop it.
- "type": one of "friction", "strength", "gap", "opportunity".
- "severity": for a friction or gap, one of "low", "medium", "high", "critical"; otherwise null.
- "title": a short label (<= 10 words).
- "description": one clear sentence stating the finding and its CX implication.
- "evidence": the concrete metric, figure, or verbatim that supports it (reproduce numbers exactly).
- "source_document": the document the finding comes from (its English title).

HOW TO WRITE THE TITLE AND DESCRIPTION. These are the report's most-read lines -- they become the "problems found" list a consultant scans before a client meeting. Write them the way you would say them out loud.

Make the title a statement with a verb, not a label made of stacked nouns. "Stagnant service level performance" and "Tracking limitations on user segments" name a topic; they do not tell anyone what is wrong. Say what is happening, to whom.

  WEAK    Stagnant service level performance
  BETTER  The call centre answers barely half its calls in time

  WEAK    High agent attrition impacting service
  BETTER  Most new agents leave before they finish training

  WEAK    Proactive service restoration architecture
  BETTER  The app reconnects itself after a network drop

Plain words in the description too: "use" not "utilise", "problem" not "pain point", "start" not "initiate". Never "leverage", "holistic", "robust", "landscape", "at scale", "operational excellence". Keep the sentence under about 25 words and put the number in it.

Rules: ground every finding in the analyses; reproduce figures exactly; one finding per distinct issue (never split or duplicate one issue). Write the "title", "description" and "evidence" in the report's output language -- default English, but if the user's instruction requests another language, use that language for these fields (the JSON keys, "type", "severity" and "capability_code" always stay in English).

Output ONLY valid JSON in EXACTLY this shape -- no markdown, no prose, no code fences:
{{"findings": [ {{"capability_code": "...", "type": "...", "severity": "...", "title": "...", "description": "...", "evidence": "...", "source_document": "..."}} ]}}
"""


# The map step is deliberately extractive, not interpretive: its whole job is to carry
# every number and fact forward intact so the final synthesis has nothing to invent.
MAP_SYSTEM_PROMPT = """You are a meticulous research analyst preparing extraction notes for a senior partner's report.

You are given ONE section of ONE source document. Produce dense, faithful extraction notes that preserve EVERYTHING an executive analysis would need:

- Every financial figure, percentage, currency amount, date, KPI, and named metric -- reproduced EXACTLY as written, with its label and unit.
- Every table -- reproduced as a compact markdown table, values unchanged.
- Every named entity (companies, products, people, segments, systems, regulations) and the claim attached to it.
- Section headings and the structure of the material.
- Any stated conclusion, risk, trend, or recommendation.

RULES:
- Do NOT summarize away numbers. Do NOT round. Do NOT editorialize or add analysis -- that happens later.
- If the section is boilerplate (headers/footers/legal), say so in one line rather than padding.
- Output structured markdown notes only. Be complete but non-repetitive.
"""

REDUCE_CONDENSE_SYSTEM_PROMPT = """You are consolidating multiple extraction-note fragments that all come from THE SAME document.

Merge them into a single coherent set of notes for that document, preserving every figure, table, date, entity, and stated conclusion exactly. Remove only literal duplication. Do not add analysis. Output markdown notes only.
"""


CHAT_SYSTEM_PROMPT = """You are the EY CX Desk Research Assistant — a sharp, senior customer-experience
research analyst embedded in the user's document workspace. You help them explore, understand, and
reason about the documents they have uploaded to the current session.

You handle every kind of message naturally:
- Greetings, thanks, and small talk → respond briefly and warmly; no citations needed.
- Questions about the workspace itself ("what documents do I have?", "what can you do?") → answer
  from the session document list provided to you.
- Questions about the documents' content, data, or findings → answer from the retrieved excerpts.
- Analytical / open-ended asks ("what are the risks?", "compare X and Y", "summarize the strategy")
  → synthesize across the excerpts; reason, don't just quote.

How to answer well:
1. Ground every factual claim about the documents in the retrieved excerpts, and cite the source
   inline as `[filename, p<page>]`. Never invent a citation or a figure.
2. When excerpts are provided but don't cover the question, say so plainly, then offer what the
   documents DO contain that's relevant — be helpful, not a dead end.
3. When no excerpts are provided (e.g. small talk or a workspace question), just answer directly.
4. Be concise and analytical, in a professional EY consulting tone. Use short markdown — bold key
   numbers, bullet lists for multiple points. Answer in the user's language.
5. Use the conversation history to resolve follow-ups ("and in 2025?", "why?") in context.
"""


def _chunk_text(text: str, size: int) -> list[str]:
    """Split text into <= ``size`` char chunks, preferring paragraph boundaries.

    Keeps whole paragraphs together where possible so a table or figure is not sliced
    down the middle, which would strand half its numbers in a different map call.
    """
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in text.split("\n\n"):
        para_len = len(para) + 2
        if current_len + para_len > size and current:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        if para_len > size:
            # A single oversized paragraph (e.g. a giant table) is hard-split.
            for i in range(0, len(para), size):
                chunks.append(para[i : i + size])
            continue
        current.append(para)
        current_len += para_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _normalize_report(text: str) -> str:
    """Deterministic cleanup the LLM cannot be fully trusted to do itself:
    strip markdown horizontal rules (`---`/`***`), normalise "### Deep-dive: X" headings to
    "### X", and collapse runs of blank lines. Structure-preserving."""
    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.fullmatch(r"[-*_]{3,}", stripped):
            continue  # drop a horizontal rule on its own line
        m = re.match(r"^(#{2,4})\s*Deep[\s-]?dive\s*[:\-]\s*(.+)$", line, flags=re.IGNORECASE)
        if m:
            line = f"{m.group(1)} {m.group(2).strip()}"
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _render_cx_mapping(findings: list[dict]) -> str:
    """Render the structured CX findings grouped by axis -> capability -- a human view of the same
    data the issue log consumes structurally. Only CX-relevant findings appear here (general
    business content stays in the narrative report, per the mapping's escape hatch)."""
    if not findings:
        return ""
    from app.services.cx_framework import get_framework

    def _clip(text: str, limit: int) -> str:
        """Collapse whitespace, escape pipes, and truncate at a WORD boundary (never mid-word)."""
        t = " ".join((text or "").replace("|", "/").split())
        if len(t) <= limit:
            return t
        return t[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"

    out = [
        "## CX Capability Mapping",
        "",
        "*The customer-experience findings from the documents above, organised by CX capability. "
        "Purely operational or financial detail is left in the narrative and not repeated here.*",
        "",
    ]
    for axis in get_framework():
        axis_items = [f for f in findings if f.get("axis") == axis.name]
        if not axis_items:
            continue
        out += [f"### {axis.name}", "",
                "| Capability | Type | Severity | Finding | Evidence | Source |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |"]
        # Order rows by the capability order within the axis, then any leftovers.
        cap_order = [name for _, name in axis.capabilities]
        for f in sorted(axis_items, key=lambda x: cap_order.index(x["capability"]) if x.get("capability") in cap_order else 99):
            cap = _clip(f.get("capability") or "—", 40)
            # Show the finding itself (statement + implication), not a terse label.
            finding = _clip(f.get("description") or f.get("title") or "", 230)
            ev = _clip(f.get("evidence") or "", 180)
            src = _clip(f.get("source_document") or "", 55)
            out.append(f"| {cap} | {f.get('type','')} | {f.get('severity') or '—'} | {finding} | {ev} | {src} |")
        out.append("")
    return "\n".join(out).strip()


class DeskResearchSynthesizer:
    """Full-document report generation and session RAG chatbot queries."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._gateway = build_mistral_gateway(self._settings)

    # ------------------------------------------------------------------ #
    #  Executive report (map-reduce)                                       #
    # ------------------------------------------------------------------ #

    async def generate_executive_report(
        self,
        documents: List[ProcessedDocument],
        session_title: Optional[str] = None,
        language: str = "English",
        user_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate the cross-document executive report.

        Small sessions take a single LLM pass. Larger ones are handled map-reduce:
        each document (chunked if long) is extracted in parallel, then those notes are
        synthesized into the final report -- so no document is ever silently dropped.
        """
        # "Has content" must mean prose, not merely non-whitespace. A scanned PDF that docling
        # turned into three ``<!-- image -->`` placeholders passes a .strip() test, and then gets
        # counted as a document analysed and handed to the deep-dive model, which writes a
        # plausible analysis of a document it was shown no text from.
        from app.services.desk_research.extractor import has_readable_text

        usable = [d for d in documents if has_readable_text(d.markdown)]
        skipped = [d for d in documents if d not in usable]
        if skipped:
            logger.warning(
                "Excluding %d document(s) with no readable text from the report: %s",
                len(skipped), ", ".join(d.filename for d in skipped),
            )
        if not usable:
            return {"status": "error", "message": "No readable document content to analyze."}

        total_chars = sum(len(d.markdown) for d in usable)
        title = session_title or "Desk Research Session"

        # Per-document sources (raw markdown, or extraction notes for very long docs), then a
        # tight cross-document Part 1 + an UNCAPPED per-document deep-dive for Part 2. Generating
        # Part 2 one document at a time is what stops the final call from having to compress the
        # whole set into a single capped answer -- which is where detail used to be lost.
        cx_findings: list[dict] = []
        cx_calls = 0
        from app.services.observability.llm_metrics import llm_context
        with llm_context(feature="desk.report", kind="run"):
            sources, map_calls = await self._build_sources(usable)
            part1_data, deep_dives, reduce_calls = await self._assemble_report(sources, title, language, user_context)
            # Structured CX-capability mapping (feeds the issue log); rendered into the report too.
            # Structured only. It feeds the issue log; rendering it into the report added a
            # capability table nobody reading the overview wanted.
            cx_findings, cx_calls = await self._generate_cx_mapping(
                deep_dives or [txt for _, txt in sources], language, user_context
            )
        map_calls += reduce_calls + cx_calls
        strategy = "structured"

        from app.services.desk_research import report_overview

        # The overview is the model's prose plus Python's counts. Built after the CX mapping
        # because every figure in it is derived from those findings.
        overview = report_overview.build_overview(part1_data, cx_findings, len(usable))
        raw_fallback = str(part1_data.get("_raw_markdown") or "").strip()
        report = raw_fallback or report_overview.render_markdown(overview, title)
        if raw_fallback:
            overview = None   # nothing structured to lay out; the UI renders the markdown

        if not report.strip():
            return {"status": "error", "message": "Report generation failed."}

        # Repair any UTF-8-as-Latin-1 mojibake (curly quotes, dashes, echoed Arabic filenames),
        # then a deterministic cleanup (strip `---` rules, normalise headings) the LLM can't be
        # trusted to do consistently. Both structure-preserving.
        report = _normalize_report(repair_encoding(report))

        return {
            "status": "success",
            "document_count": len(usable),
            "total_chars_analyzed": total_chars,
            "strategy": strategy,
            "map_calls": map_calls,
            "report_markdown": report,
            "report_overview": overview,   # the structured half the UI lays out
            "document_analyses": deep_dives,   # per-document detail: issue-log input, not shown
            "cx_findings": cx_findings,        # structured — the issue log consumes this directly
        }

    async def _build_sources(
        self,
        documents: List[ProcessedDocument],
    ) -> tuple[list[tuple[str, str]], int]:
        """One comprehensive source blob per document, in document order: the raw markdown when
        it fits a map chunk, else faithful extraction notes (map + condense) so a long document
        is never truncated. Returns (sources, map_calls)."""
        sources: list[tuple[str, str]] = []
        map_calls = 0
        for doc in documents:
            md = (doc.markdown or "").strip()
            if len(md) <= _MAP_CHUNK_CHARS:
                sources.append((doc.filename, md))
            else:
                notes, calls = await self._extract_document_notes(doc)
                map_calls += calls
                sources.append((doc.filename, notes or md[:_MAP_CHUNK_CHARS]))
        return sources, map_calls

    async def _extract_document_notes(self, doc: ProcessedDocument) -> tuple[str, int]:
        """Map a long document into faithful, extractive notes (every figure and table preserved),
        condensing multi-chunk output back into one note set. Returns (notes, calls)."""
        chunks = _chunk_text(doc.markdown, _MAP_CHUNK_CHARS) or [""]
        semaphore = asyncio.Semaphore(_MAP_CONCURRENCY)

        async def _map_one(i: int, chunk: str) -> str:
            label = doc.filename if len(chunks) == 1 else f"{doc.filename} (part {i}/{len(chunks)})"
            async with semaphore:
                return await self._report_llm(
                    MAP_SYSTEM_PROMPT, f"Source document: {label}\n\nSECTION CONTENT:\n{chunk}"
                )

        parts = await asyncio.gather(*[_map_one(i, c) for i, c in enumerate(chunks, 1)])
        calls = len(chunks)
        good = [p.strip() for p in parts if p and not p.startswith("Error:")]
        merged = "\n\n".join(good)
        if len(good) > 1 and len(merged) > _MAP_CHUNK_CHARS:
            merged = await self._report_llm(
                REDUCE_CONDENSE_SYSTEM_PROMPT, f"Document: {doc.filename}\n\nFRAGMENTS:\n{merged}"
            )
            calls += 1
        return merged.strip(), calls

    async def _assemble_report(
        self,
        sources: list[tuple[str, str]],
        title: str,
        language: str,
        user_context: Optional[str],
    ) -> tuple[str, int]:
        """Part 2 FIRST (one deep-dive per document, in parallel), then Part 1 synthesised FROM
        those deep-dives -- so Part 1's figures are anchored to Part 2 and cannot contradict it."""
        calls = 0
        focus = ""
        if user_context and user_context.strip():
            focus = f'\nUSER FOCUS FOR THIS ANALYSIS: "{user_context.strip()}"\n'

        # ── Part 2: one deep-dive per document, in parallel ─────────────
        semaphore = asyncio.Semaphore(_MAP_CONCURRENCY)

        async def _deep_dive(i: int, filename: str, text: str) -> tuple[int, str]:
            prompt = (
                f"Language requested: {language}\n{focus}\n"
                f"Document filename (for your reference only; do NOT put it in the heading): {filename}\n\n"
                f"FULL DOCUMENT CONTENT:\n{text.strip()}\n\n"
                "Write this document's deep-dive subsection, per the system guidelines -- cover and "
                "explain every IMPORTANT point as one clean, readable section."
            )
            async with semaphore:
                out = await self._report_llm(DEEPDIVE_SYSTEM_PROMPT, prompt)
            return i, out

        dd = await asyncio.gather(*[_deep_dive(i, fn, txt) for i, (fn, txt) in enumerate(sources, 1)])
        calls += len(sources)
        deep_dives = [out.strip() for _, out in sorted(dd) if out and not out.startswith("Error:")]

        # ── Part 1: synthesised FROM the deep-dives so its numbers match Part 2 exactly ──
        if deep_dives:
            part1_source = "\n\n".join(deep_dives)
            if len(part1_source) > _REDUCE_CHAR_BUDGET:  # very large set -> condense first
                part1_source = await self._report_llm(REDUCE_CONDENSE_SYSTEM_PROMPT, part1_source)
                calls += 1
            part1_prompt = (
                f"Language requested: {language}\nSession Title: {title}\n{focus}\n"
                "Below are the per-document DEEP-DIVE analyses already written for Part 2 of this report. "
                "Write Part 1 (the cross-document executive synthesis) so that it is FULLY CONSISTENT with "
                "them: every figure you cite must match the deep-dives exactly (same value, period, region). "
                "Never introduce a number that contradicts a deep-dive.\n\n"
                # The count is stated because the model has been leaving documents out of the
                # table while still citing them as sources elsewhere in the report -- so a reader
                # meets a source that appears nowhere in the list of what was read.
                f"There are {len(deep_dives)} deep-dives below, one per document. Your \"documents\" "
                f"array must have exactly {len(deep_dives)} entries, one for each, in this order. "
                "Include a document even if it is short or you found little in it.\n\n"
                f"{part1_source}\n\n"
                "Generate Part 1 now, following the system guidelines."
            )
        else:
            # Fallback: no deep-dive succeeded -- synthesise Part 1 from the raw sources.
            part1_source = "\n\n".join(
                f"=== DOCUMENT {i}: {fn} ===\n{txt.strip()}" for i, (fn, txt) in enumerate(sources, 1)
            )
            part1_prompt = self._compose_report_prompt(
                title, language, user_context, part1_source, from_notes=True
            )

        from app.services.cx_framework import framework_card
        from app.services.llm.utils import extract_json

        # The framework goes in the system prompt so the model reads the documents against the
        # same nine capabilities the issue log and the maturity assessment use.
        system = PART1_SYSTEM_PROMPT_TEMPLATE.format(framework=framework_card())
        raw_part1 = await self._report_llm(system, part1_prompt)
        calls += 1

        try:
            part1_data = extract_json(raw_part1)
            if not isinstance(part1_data, dict):
                raise ValueError("Part 1 was not a JSON object")
        except Exception:
            # A provider that answers with prose instead of JSON must not cost the whole report.
            # The structured overview is lost -- the UI falls back to rendering the markdown -- but
            # the text the model did write is kept, and the deep-dives and CX findings are
            # untouched either way.
            logger.warning("Part 1 did not return JSON; keeping its text as the report body")
            part1_data = {"_raw_markdown": (raw_part1 or "").strip()}

        # ── Assemble ────────────────────────────────────────────────────
        # The report is Part 1 ONLY. The per-document deep-dives are returned alongside it and
        # stored separately: they are the right granularity for the issue log (one call per
        # document yields ~3x the issues of one bundled call) and the wrong thing to read, since
        # they restate each document at length.
        return (part1_data if isinstance(part1_data, dict) else {}), deep_dives, calls

    async def _generate_cx_mapping(self, blocks: list[str], language: str, user_context: Optional[str] = None) -> tuple[list[dict], int]:
        """Map findings onto the real CX capability framework as STRUCTURED data -- the machine
        contract the issue log consumes. Findings that aren't about a CX capability are dropped
        (the escape hatch), so this never force-fits general business content. The markdown section
        is only a rendering of this; each finding carries its ``axis`` + ``capability``."""
        blocks = [b for b in blocks if b and b.strip()]
        if not blocks:
            return [], 0
        from app.services.cx_framework import framework_card, resolve_capability
        from app.services.llm.utils import extract_json

        src = "\n\n".join(blocks)
        if len(src) > _REDUCE_CHAR_BUDGET:
            src = src[:_REDUCE_CHAR_BUDGET]
        system = CX_MAPPING_SYSTEM_PROMPT_TEMPLATE.format(framework=framework_card())
        focus = (
            f'\nUSER INSTRUCTION (authoritative for the output language of title/description/evidence): '
            f'"{user_context.strip()}"\n' if (user_context and user_context.strip()) else ""
        )
        raw = await self._report_llm(
            system,
            f"Output language: {language}{focus}\nDOCUMENT ANALYSES:\n{src}\n\nOutput the CX findings JSON now.",
        )
        try:
            data = extract_json(raw)
            findings = data.get("findings", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        except Exception:
            logger.warning("CX capability mapping: JSON parse failed")
            return [], 1

        valid_types = {"friction", "strength", "gap", "opportunity"}
        valid_sev = {"low", "medium", "high", "critical"}
        out: list[dict] = []
        dropped = 0
        for f in findings:
            if not isinstance(f, dict) or not str(f.get("description", "")).strip():
                continue
            capability, axis = resolve_capability(f.get("capability_code") or f.get("capability"))
            if capability is None:  # escape hatch: not a CX-capability finding -> drop from mapping
                dropped += 1
                continue
            ftype = str(f.get("type", "")).strip().lower()
            sev = str(f.get("severity", "") or "").strip().lower()
            out.append({
                "axis": axis,
                "capability": capability,
                "type": ftype if ftype in valid_types else "friction",
                "severity": sev if sev in valid_sev else None,
                "title": str(f.get("title", "")).strip(),
                "description": str(f.get("description", "")).strip(),
                "evidence": str(f.get("evidence", "")).strip(),
                "source_document": str(f.get("source_document", "")).strip(),
            })
        if dropped:
            logger.info("CX mapping: kept %d findings, dropped %d as non-CX", len(out), dropped)
        return out, 1

    def _compose_report_prompt(
        self,
        title: str,
        language: str,
        user_context: Optional[str],
        context: str,
        *,
        from_notes: bool = False,
    ) -> str:
        focus = ""
        if user_context and user_context.strip():
            focus = (
                "\nUSER SPECIFIC FOCUS AND GOAL FOR THIS ANALYSIS:\n"
                f'"{user_context.strip()}"\n'
                "(Prioritize and directly address this request throughout the report.)\n"
            )
        source_label = (
            "Below are faithful EXTRACTION NOTES prepared from every uploaded document "
            "(all figures and tables preserved verbatim):"
            if from_notes
            else "Below is the COMPLETE EXTRACTED DATA from all uploaded documents in this session:"
        )
        return (
            f"Language requested: {language}\n"
            f"Session Title: {title}\n"
            f"{focus}\n"
            f"{source_label}\n\n"
            f"{context}\n\n"
            "Generate the comprehensive, executive-level Desk Research Synthesis Report "
            "following the system guidelines."
        )

    # ------------------------------------------------------------------ #
    #  Session chatbot (secondary use case)                                #
    # ------------------------------------------------------------------ #

    async def chat_with_session(
        self,
        documents: List[ProcessedDocument],
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Answer a query against session documents with agentic RAG.

        The model first decides whether the documents are needed (greetings/meta answered
        directly; content questions grounded with citations), retrieves multi-query when they
        are, and answers with a defined analyst role and the conversation history. Falls back to
        legacy keyword-over-blocks retrieval only if the engine path fails -- so it never hard-fails.
        """
        if not documents:
            return {"answer": "No documents uploaded in this session to search.", "sources": []}

        if session_id:
            try:
                from app.services.desk_research import rag_index
                from app.services.rag import engine

                namespace = rag_index.ensure_index(session_id, documents)
                # Always-available manifest so "what documents do I have?" needs no retrieval.
                manifest = ", ".join(repair_encoding(d.filename) for d in documents)
                preamble = f"Documents in this session: {manifest}."
                # Let the agent know the report exists and how to cite it.
                from app.services.desk_research import session_manager

                _info = session_manager.get_session(session_id)
                if _info and _info.report_markdown:
                    preamble += " An executive report has been generated for this session; it is searchable and cited as [Executive Report]."
                result = await engine.agentic_answer(
                    query,
                    self._chat_llm,
                    answer_system_prompt=CHAT_SYSTEM_PROMPT,
                    context_source=engine.rag_context_source(
                        namespace, k=8, header="Relevant excerpts from the session's documents:"
                    ),
                    history=chat_history,
                    preamble=preamble,
                )
                return {
                    "answer": repair_encoding(result["answer"]),
                    "sources": list(dict.fromkeys(repair_encoding(s) for s in result["sources"])),
                    "retrieved_blocks_count": result["retrieved_count"],
                    "used_search": result.get("used_context", False),
                }
            except Exception:
                logger.warning("RAG chat path failed for %s; using keyword fallback.", session_id, exc_info=True)

        # ── Legacy fallback: keyword overlap over raw blocks ──
        relevant_blocks = self._retrieve_relevant_blocks(documents, query, top_k=12)

        context_lines, sources = [], []
        for b in relevant_blocks:
            src_str = f"{b['filename']} (Page/Sheet {b['page']})"
            sources.append(src_str)
            context_lines.append(f"--- [Source: {src_str}] ---\n{b['text']}")

        user_prompt = f"Context from Session Documents:\n\n" + "\n\n".join(context_lines) + f"\n\nUser Question: {query}"
        answer = await self._chat_llm(CHAT_SYSTEM_PROMPT, user_prompt)

        return {
            "answer": repair_encoding(answer),
            "sources": list(dict.fromkeys(repair_encoding(s) for s in sources)),
            "retrieved_blocks_count": len(relevant_blocks),
        }

    def _retrieve_relevant_blocks(
        self,
        documents: List[ProcessedDocument],
        query: str,
        top_k: int = 12,
    ) -> List[Dict[str, Any]]:
        """Keyword-overlap block retrieval. (Semantic retrieval is the planned upgrade.)"""
        q_words = {w.lower() for w in query.split() if len(w) > 2}
        scored_blocks = []
        for doc in documents:
            for b in doc.blocks:
                if not b.text or len(b.text.strip()) < 10:
                    continue
                b_words = {w.lower() for w in b.text.split()}
                score = len(q_words & b_words)
                if score > 0:
                    scored_blocks.append(
                        {"filename": doc.filename, "page": b.page_number or 1, "text": b.text, "score": score}
                    )
        scored_blocks.sort(key=lambda x: x["score"], reverse=True)

        if not scored_blocks:
            for doc in documents[:2]:
                for b in doc.blocks[:5]:
                    if b.text and len(b.text.strip()) > 10:
                        scored_blocks.append(
                            {"filename": doc.filename, "page": b.page_number or 1, "text": b.text, "score": 0}
                        )
        return scored_blocks[:top_k]

    # ------------------------------------------------------------------ #
    #  LLM plumbing                                                        #
    # ------------------------------------------------------------------ #

    async def _report_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Report/map/reduce LLM call with a resilient provider LOOP:
            Mistral -> OpenAI -> Gemini,  cycled twice with a backoff between passes (which lets a
            Mistral 429 rate-limit reset before we try it again).
        Returns the first good response. If every provider fails on both passes, returns an
        'Error: ...' sentinel -- the caller turns that into an error the frontend shows."""
        # The loop itself lives in app/services/llm/failover.py so the interview-guide generator
        # uses the identical behaviour rather than a second, drifting copy of it.
        from app.services.llm.failover import complete_with_failover

        return await complete_with_failover(
            system_prompt, user_prompt, primary=self._mistral_report, label="desk.report"
        )

    async def _mistral_report(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Primary provider. The gateway already retries with backoff on 429 internally."""
        return await self._gateway.chat_messages([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

    async def _chat_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Chat Q&A: Moonshot/Kimi if configured, else Mistral gateway, else Gemini."""
        settings = self._settings
        if settings.moonshot_api_key:
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    res = await client.post(
                        settings.moonshot_base_url.rstrip("/") + "/chat/completions",
                        headers={"Authorization": f"Bearer {settings.moonshot_api_key}"},
                        json={
                            "model": settings.moonshot_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        },
                    )
                    if res.status_code == 200:
                        content = ((res.json().get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
                        if content:
                            return content
                    else:
                        logger.warning("Moonshot chat returned %d: %s", res.status_code, res.text[:120])
            except Exception as exc:
                logger.warning("Moonshot chat failed: %s", exc)

        # Fall back to the same report pipeline (gateway → Gemini).
        return await self._report_llm(system_prompt, user_prompt)

    async def _gemini_failover(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Env-only Gemini failover. No hardcoded credentials: silent no-op if unconfigured."""
        keys = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
        if not keys:
            return None
        # Newest-first text models (verified against the live ListModels API, Jul 2026);
        # prefer full flash for synthesis quality, then lite for availability, then a
        # self-tracking 'latest' alias. Override via GEMINI_TEXT_MODELS.
        models = [
            m.strip()
            for m in os.getenv(
                "GEMINI_TEXT_MODELS",
                "gemini-3.5-flash,gemini-3.1-flash-lite,gemini-2.5-flash,gemini-flash-latest",
            ).split(",")
            if m.strip()
        ]
        async with httpx.AsyncClient(timeout=90.0) as client:
            for key in keys:
                for model in models:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                    payload = {
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                    }
                    try:
                        res = await client.post(url, json=payload)
                        if res.status_code == 200:
                            parts = res.json()["candidates"][0]["content"]["parts"]
                            text = "".join(p.get("text", "") for p in parts).strip()
                            if text:
                                logger.info("Gemini failover succeeded with %s", model)
                                return text
                    except Exception:
                        continue
        return None
# Singleton
_synthesizer: Optional[DeskResearchSynthesizer] = None


def get_synthesizer() -> DeskResearchSynthesizer:
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = DeskResearchSynthesizer()
    return _synthesizer
