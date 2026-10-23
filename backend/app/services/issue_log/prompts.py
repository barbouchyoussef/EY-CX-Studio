"""Prompt construction for the issue log.

Every rule below is traceable to something measured while building this. The comments record
which, because a prompt without that history looks arbitrary and gets "tidied" back into a worse
version six months later.

  - findings came out sentence-shaped 6-18% of the time  -> FORM, with the client's own rewrites
  - the model wrote one issue per COMPLAINANT on reviews -> VOICE mode, 4.2x too many issues
  - it invented deficiencies from strategy decks         -> the unmet-ambition rule
  - output drifted into the source's language            -> an explicit output language
  - investigations were terse and abstract               -> the clarity rules and worked examples

Asking a model to "be concrete" changed nothing (vague rate 25% -> 28%). Requiring it to QUOTE
the line it relies on worked, and the quote is verifiable without a model. Structural obligations
beat judgemental ones.
"""

from __future__ import annotations

from typing import Literal

from app.services.issue_log import taxonomy

Mode = Literal["document", "voice"]

PROMPT_VERSION = "v5"


# --------------------------------------------------------------------------------------------
# Shared blocks
# --------------------------------------------------------------------------------------------

GOLD = """WORKED EXAMPLES -- real rows from a finished client log. Match this register.

  finding:       Lack of omnichannel integration
  investigation: Customers interact with direct sales centers, vendors, mobile sellers, and
                 online platforms, but no omnichannel system ensures a seamless experience.

  finding:       Lack of structured issue-handling systems
  investigation: Sales agents rely on manual reporting (via email or calls) to escalate technical
                 issues due to the absence of an automated tracking and resolution system. This
                 increases customer effort, delays visibility into issue status, and limits the
                 ability to provide timely and transparent updates to the customer.

  finding:       Low digital channel adoption
  investigation: Despite initiatives like free quota promotions and daily login incentives,
                 customers show disinterest in downloading and using the digital app due to
                 perceived complexity and lack of inherent value."""


FORM = """HOW TO WRITE THE "finding"
The client revised their own log to enforce one rule and wrote it in the margin: "Findings should
be stated as facts, leave explanations to descriptions" and "Use strategic adjectives (lack, not
weak)". Follow it exactly.

A finding is a NOUN PHRASE naming the deficiency. Three to eight plain words, no verb, no clause,
no full stop. Their own before/after rewrites:

  NO   Customer journeys are fragmented due to lack of omnichannel integration.
  YES  Lack of omnichannel integration

  NO   Manual processes create inefficiencies and disjointed customer experiences.
  YES  Manual coordination across teams

  NO   Weak digital integration lowers customer engagement online.
  YES  Limited integration of digital customer journeys

Open with a deficiency word: Lack of, Absence of, Limited, Inconsistent, Fragmented, Manual,
Unstructured, Undefined, Duplicate, Delayed, Prolonged. Avoid judgement words that carry no
information: weak, poor, bad, suboptimal, problematic.

Write plain text. No markdown, no asterisks, no bold -- these land in a spreadsheet cell.


HOW TO WRITE THE "investigation" -- THIS IS WHERE CLARITY MATTERS MOST

Write THREE TO FIVE sentences. Longer is fine. Being short is NOT a goal; being understood is.
Assume the reader is a busy manager who has never seen the source document, will read this once
in a spreadsheet, and then decide what to do.

Cover three things, in order:
  1. WHAT IS HAPPENING -- the concrete situation, with the real numbers and names.
  2. WHO IT AFFECTS AND HOW -- the customer, the staff or the operation, in practical terms.
  3. WHY IT MATTERS -- the cost, risk or consequence if nothing changes.

RULES FOR THE WRITING
- Keep the language simple and professional. Clear business English, not academic or consulting
  English. A competent reader whose first language is not English should follow it on one read.
  Swap the heavier word for the plain one:
      erodes trust                -> customers lose trust
      undermines / hinders        -> weakens, slows down, gets in the way of
      churn                       -> customers leaving
      systemic                    -> across the business
      aggregate                   -> collect, add up
      operational downtime        -> time when the service is not working
      customer sentiment          -> what customers think
      mitigate                    -> reduce, limit
      leverage / utilise          -> use
      insufficient visibility     -> no clear view
      impacts                     -> affects
- Put the number IN the sentence. "42% of mobile visitors leave without clicking anything" beats
  "high bounce rates are observed on mobile".
- Explain any internal name the first time it appears: "the 9V ZSmart billing system", not
  "9V ZSmart". A reader outside the project does not know what it is.
- NEVER refer to the source inside the text. No "as reported in the analysis", no "the document
  states". The reader wants the fact; the source has its own column.
- One idea per sentence. Keep sentences under about 25 words. No stacked abstract nouns.
- Do not use two words where one works, and do not add a closing sentence that only restates
  what you already said in more serious-sounding language.

  NO   Digital channels exhibit high mobile and overall bounce rates, as reported in the analysis.
  YES  42% of people who open the site on a phone leave without clicking anything, and phones are
       68% of all visits. The site is hardest to use for most of the people who visit it. Anyone
       trying to check a bill on mobile is likely to give up and call the contact centre instead,
       which pushes cost onto the call centre.

  TOO HEAVY   Insufficient structured feedback mechanisms undermine the organisation's ability to
              aggregate customer sentiment, thereby impeding systemic remediation and eroding
              long-term customer trust.
  RIGHT       Customer feedback arrives by email and phone with no set process for recording it.
              Nobody can add it up, so the same complaints keep coming back without being fixed.
              Teams have no clear view of what customers are actually unhappy about."""


ANCHOR = """EVERY ISSUE MUST BE ANCHORED TO THE SOURCE
For each issue, copy into "evidence" the exact words from the source that support it -- one or
two sentences, verbatim, character for character, IN THE SOURCE'S OWN LANGUAGE. Do not
paraphrase, do not translate, do not tidy the wording.

Work in this order:
  1. Find the passage that reports a problem.
  2. Copy it verbatim into "evidence".
  3. Only then write the finding and the investigation from it.

If you cannot point to specific words in the source, THERE IS NO ISSUE. Do not write one. This
applies especially to statements that feel true of any company in this industry.

Never put profanity, an insult, a person's name, a phone number, an account number or an address
into any field. This log is a client deliverable.

WHAT IS NOT AN ISSUE -- do not emit these
- A metric with no deficiency. "Tablet users are 5% of sessions" is a number, not a problem.
- A recommendation. The fix belongs in a different document.
- A strength or anything positive.
- AN UNMET AMBITION. A strategy or vision document listing targets for a future year describes
  what the company WANTS, not what it does wrong. "The 2026 plan targets full 5G coverage" is a
  goal; writing "Insufficient 5G availability" invents a deficiency the source never reported.
  Record a gap only where the material shows a failure happening NOW, and quote it.
- A restatement of another issue you already wrote in this response."""


CLASSIFY = """CLASSIFICATION
Choose "strategic_dimension" and "sub_category" using the DEFINITIONS in the taxonomy below, not
the labels alone. The sub-category MUST belong to the dimension you chose.

Classify by WHERE IN THE BUSINESS the deficiency lives, not by who feels the consequence. Almost
every issue eventually affects the customer; that does not make everything Customer Experience.
A network outage is Systems and Technology even though customers suffer it. An undocumented
escalation rule is Processes & Policies even though it slows the call centre.

Set "channel" only if the source explicitly names one; otherwise null."""


SEVERITY = """SEVERITY -- grade each issue and justify the grade

  critical  Customers cannot use a service they pay for, or the company cannot bill, measure or
            account for something correctly. Money or trust is being lost right now.
  high      Significant, repeated effort or cost imposed on customers or staff. Works eventually,
            but badly, and often.
  medium    Degrades the experience but a workaround exists and the impact is contained.
  low       Isolated, cosmetic, or affecting a small group in a minor way.

Put the grade in "severity" and ONE plain sentence in "severity_reason" saying what drove it --
scale, money, frequency, or risk. A reviewer must be able to disagree with the grade by reading
that sentence. Do not grade on how alarming the wording sounds; grade on consequence."""


YIELD = """HOW MANY ISSUES TO RECORD
Record every distinct problem this source actually contains -- no more, and no fewer. Do not aim
for a number. A rich operational report may hold fifteen genuine deficiencies; a short memo may
hold two; a document that reports no problems yields none, and returning an empty list is the
correct answer there.

The only hard ceiling is this: a single source almost never contains more than TWENTY good,
non-redundant issues. If you are past twenty, you are no longer finding new problems -- you are
splitting one problem into variants, or recording details and figures as if they were
deficiencies. Stop, merge them back down, and return the distinct set.

Completeness means every DISTINCT PROBLEM here is represented ONCE. It does not mean producing as
many rows as possible. A consultant has to read and act on every line you write, so a row that
restates the one above it costs them time and earns nothing."""


VOICE_MODE = """WHAT THIS SOURCE IS: individual customer reports (reviews, comments, complaints).

Dozens of customers are describing THE SAME small number of underlying business problems in their
own words. Find those problems; do not transcribe the complaints.

ONE ISSUE PER PROBLEM, NOT PER CUSTOMER. This is the most important rule for this source.
  WRONG -- four rows, four customers, one problem:
      Two-month unresolved internet outage despite daily contact
      Extended unresolved ADSL outage despite paid subscription
      More than one week of unresolved internet disconnection
      Prolonged loss of home internet for months
  RIGHT -- one row:
      finding:       Prolonged unresolved service outages
      investigation: Customers report internet and ADSL outages lasting from one week to two
                     months despite repeated contact with support. Service is not restored and
                     billing continues, so customers pay for a service they cannot use.
      reports:       31

Work like this:
  1. Read every report and identify the recurring problems behind them.
  2. Write ONE issue per problem, at the level a manager could act on.
  3. In "reports", put how many separate customers raised it. That number is the evidence.
  4. For "evidence", follow the rule below. Do NOT quote a customer.

EVIDENCE FOR THIS SOURCE TYPE -- NEVER QUOTE A CUSTOMER
Customer reviews contain insults, profanity, personal names, phone numbers and account details.
None of that belongs in a document that goes to the client, and one crude quote undoes the
credibility of everything around it.

Put in "evidence" the line from the RECURRING FRICTION THEMES section that supports the issue.
Those are already aggregates and they carry the counts:
      evidence: "Qualite de la prise en charge client (raised in 44 reviews, 38.6% of negative
                 sentiment)"

If no theme line covers the issue, write ONE neutral factual sentence describing what the reports
say, including how many raised it. Never reproduce a customer's words, never name a person, and
never include a phone number, an account number or an address.

Generalise to the level of a business problem. Do not name individual customers, do not carry one
person's specific duration into the finding, and never write two issues a manager would fix with
the same action.

However many reviews this source contains -- fifty or five hundred -- they collapse into a small
set of underlying problems. Ten is already a lot; past twenty you are transcribing complaints
rather than diagnosing.

If the source also lists RECURRING FRICTION THEMES computed from these reviews, treat them as the
analyst's own tally of the same material: they tell you which problems are real and how widespread
each one is. Use their counts for "reports". Do not write a separate issue for a theme and again
for the reviews behind it -- they are the same problem."""


DOCUMENT_MODE = """WHAT THIS SOURCE IS: an operational report, analysis or internal document.

You are not cataloguing what is wrong with this DOCUMENT. You are diagnosing what is wrong with
the BUSINESS, using this document as your evidence. Those produce very different logs, and only
the second one is worth a consultant's time.

WORK IN THIS ORDER. Do not start writing issues until you have finished step 1.

STEP 1 -- Read the whole document first and list the BUSINESS PROBLEMS it reveals.
A business problem is something a director would recognise, own, and be able to commission work
against: "we cannot measure call quality reliably", "our billing migration lost operational
data", "our website does not work for the phones most customers use". Expect THREE TO EIGHT of
them in a substantial document. A short memo may hold one.

STEP 2 -- For each business problem, gather the details in the document that prove it.
Duplicated criteria, totals that do not add up, undefined thresholds, a figure that dropped:
these are the PROOF, and they belong in the investigation. They are never issues by themselves.

THE TEST THAT DECIDES IT: would these two candidate issues be closed by THE SAME piece of work?
If yes, they are ONE issue. Rebuilding the call quality scoring framework fixes the duplicated
criteria, the weights that total 50 instead of 100, and the undefined threshold all at once --
so that is one issue, not three.

  WRONG -- four rows, all closed by the same piece of work:
      Duplicate evaluation criteria in quality scoring framework
      Inconsistent weight sum in quality score calculation
      Ambiguous quality threshold definition
      Unclear call response time standard

  RIGHT -- one row, with the details as proof:
      finding:       Unreliable call quality measurement
      investigation: The framework used to score call quality cannot produce a trustworthy
                     result. Two criteria are listed twice with different weights (10 and 6),
                     the weights add up to 50 while scores are reported out of 100, and the
                     threshold for an acceptable call is never defined. Supervisors cannot tell
                     whether an agent is performing well, so the 75% target the company reports
                     against does not mean anything.

  WRONG:  Tablet users represent only 5% of website sessions
  RIGHT:  (not an issue at all -- a number with no deficiency described)

Keep every figure, system name and date in the investigation. They are what make the issue
credible and let a client check it. What changes is the LEVEL of the finding: name the problem
the business has, not the fault in the paperwork.

EVIDENCE FOR THIS SOURCE TYPE
Quote ONE complete sentence from the document that a reader can find and check -- the sentence
that most directly shows the problem. Not a fragment, not a stitched-together phrase, and never
a heading on its own. Copy it exactly as written, in the document's own language, but leave out
formatting marks such as asterisks. If the strongest proof is a figure, quote the sentence that
contains it.

Set "reports" to 1 for this source type."""


_SCHEMA = ('{"issues": [{"finding": "...", "investigation": "...", "evidence": "...", '
           '"reports": <number>, "severity": "critical|high|medium|low", '
           '"severity_reason": "...", "strategic_dimension": "...", "sub_category": "...", '
           '"channel": null, "page": null}]}')


PAGE_BLOCK = """PAGE
Desk-research sources may carry page references written as `(p. 4)`. When the text supporting
an issue shows one, put that number in "page" as a plain integer. When it does not, set "page"
to null. Never infer or estimate a page: a wrong citation sends a consultant to the wrong place
and is worse than none. Sources other than documents have no pages -- always null there."""


def _language_block(language: str) -> str:
    return f"""LANGUAGE
Write "finding", "investigation" and "severity_reason" in {language}, regardless of the language
of the source. Translate faithfully and never mix languages between issues. "evidence" is the one
exception: it stays verbatim in the source's original language."""


def generate_system(mode: Mode, language: str = "English") -> str:
    return "\n\n".join([
        "You are a customer-experience consultant compiling an ISSUE LOG for a client "
        "engagement. You are working through ONE source and must identify the real problems it "
        "reveals.\n\nAn issue is a NAMED DEFICIENCY in how the business operates today.",
        VOICE_MODE if mode == "voice" else DOCUMENT_MODE,
        YIELD, ANCHOR, FORM, CLASSIFY, SEVERITY,
        PAGE_BLOCK,
        _language_block(language),
        GOLD,
        "OUTPUT\nReturn ONLY a JSON object, no prose and no code fence:\n" + _SCHEMA,
    ])


def sweep_system(mode: Mode, language: str = "English") -> str:
    return "\n\n".join([
        "You are reviewing an issue log another analyst produced from a source, to find whether "
        "a genuinely DIFFERENT problem was missed.",
        VOICE_MODE if mode == "voice" else DOCUMENT_MODE,
        "Add an issue ONLY if it would be closed by a DIFFERENT piece of work from everything "
        "already recorded. That is the whole test. A different wording, a different customer, "
        "another example, or one more faulty detail inside a problem already on the list is NOT "
        "a new issue -- it is more proof of an existing one, and it belongs nowhere.\n\n"
        "Apply that test literally. If the recorded list already says the call quality framework "
        "is unreliable, then the duplicated criteria, the weights that total 50, and the "
        "undefined threshold are all part of that same issue. Adding them separately is the "
        "single most common mistake at this step.\n\n"
        "Most of the time nothing has been missed. Returning an empty list is the expected "
        "answer and a perfectly good one. Never pad. At most THREE additions.",
        ANCHOR, FORM, CLASSIFY, SEVERITY,
        PAGE_BLOCK,
        _language_block(language),
        "OUTPUT -- use EXACTLY these field names, no others:\n" + _SCHEMA,
    ])


def context_block(client: str | None, focus: str | None = None) -> str:
    """The per-run header: who the client is, any steer from the consultant, and the taxonomy."""
    lines = [f"CLIENT: {client}" if client else "CLIENT: (unnamed)"]
    if focus and focus.strip():
        lines.append(f"ANALYSIS FOCUS FROM THE CONSULTANT: {focus.strip()}")
    lines.append("\nTAXONOMY — choose one dimension and one of ITS sub-categories, "
                 "using the definitions:")
    lines.append(taxonomy.prompt_card())
    return "\n".join(lines)


def user_prompt(chunk_rendered: str, client: str | None, focus: str | None = None) -> str:
    return (f"{context_block(client, focus)}\n"
            f"SOURCE MATERIAL — work through all of it:\n\n{chunk_rendered}\n\n"
            f"Return the JSON object now.")


def sweep_prompt(chunk_rendered: str, client: str | None, already: list[str],
                 focus: str | None = None) -> str:
    listed = "\n".join(f"- {f}" for f in already)
    return (f"{context_block(client, focus)}\n"
            f"SOURCE MATERIAL — work through all of it:\n\n{chunk_rendered}\n\n"
            f"ALREADY RECORDED:\n{listed}\n\nReturn only what was missed.")
