"""The issue-log taxonomy: strategic dimensions and their sub-categories.

This is NOT the CX maturity framework (Manage / Analyze / Improve x 9 capabilities). That one
scores how mature a capability is; this one classifies a concrete problem by the part of the
business it belongs to. A generated issue log is judged against the analyst workbook, so the
labels here mirror it exactly rather than being invented.

Reference: a telecom operator's issue log (``Issue List_V2``, 170 issues). Observed distribution across
the five dimensions actually used there: Marketing & Communication 50, Customer Service 35,
Systems and Technology 33, Processes & Policies 33, HR 19. ``Product`` is defined in the
workbook's Category Definitions sheet but unused for that client.
"""

from __future__ import annotations

# dimension -> its sub-categories, in the workbook's order.
TAXONOMY: dict[str, list[str]] = {
    "Customer Experience": [
        "Physical shops (pre-sales)",
        "Design and lifecycle",
        "Retention & Loyalty",
    ],
    "Product": [
        "Development capability",
        "Portfolio planning",
    ],
    "Marketing & Communication": [
        "Awareness",
        "Communication",
        "Branding",
    ],
    "Customer Service": [
        "Frontline operations",
        "Self-service",
        "Call center",
    ],
    "HR": [
        "Staffing",
        "HR Development",
    ],
    "Systems and Technology": [
        "Functionality",
        "UI",
        "Backend",
    ],
    "Processes & Policies": [
        "Policies and guidelines",
        "Backend operations",
    ],
}

DIMENSIONS: list[str] = list(TAXONOMY)

# Channels the workbook offers. Left optional: in the reference log 164 of 170 rows had no
# channel, so the model is told to fill it only when a source names one explicitly.
CHANNELS: list[str] = [
    "All Channels", "Website", "Mobile App", "Sales Centers", "Social Media",
    "Call center", "USSD / IVR", "Authorized Retail Shops", "Franchise Outlets",
    "Street Vendors",
]

# Definitions, transcribed from the workbook's "Category Definitions" sheet. These matter: with
# bare labels the model mis-files issues (network outages landed under Product rather than
# Systems and Technology). Where the sheet left a definition blank, a short one consistent with
# how the label is used across the 170 reference issues is supplied instead, marked (inferred).
DIMENSION_DEFS: dict[str, str] = {
    "Customer Experience":
        "All aspects of the service delivery mechanism that directly interact with customers. "
        "Barriers to effective service provision, from front-line inadequacies to challenges in "
        "self-service technologies, and the continuity of the relationship over its lifecycle.",
    "Product":
        "(inferred) The offer itself: how products and bundles are conceived, developed and "
        "planned as a portfolio. Gaps in the ability to build or evolve the offering.",
    "Marketing & Communication":
        "The effectiveness of efforts to communicate with customers: raising awareness, keeping "
        "customers clearly and positively informed, and a brand identity that resonates.",
    "Customer Service":
        "Service delivery at post-sales touchpoints: physical service centres, their equipment "
        "and layout, self-service provision, and the call centre.",
    "HR":
        "The workforce responsible for delivering customer service: employee development, "
        "performance management, clarity of roles, and staffing levels.",
    "Systems and Technology":
        "Back-end systems and operational technology that negatively affect customer experience, "
        "e.g. lack of integration or data sharing between systems, and the digital front end.",
    "Processes & Policies":
        "(inferred) How work is governed and executed internally: policies, guidelines, rules, "
        "and cross-functional or back-office operating processes.",
}

SUB_CATEGORY_DEFS: dict[str, str] = {
    "Physical shops (pre-sales)":
        "Direct interactions between agents and customers before purchase: wait times, lack of "
        "personalised service, inadequate resolution of queries.",
    "Design and lifecycle":
        "Transversal touchpoints and automated tools (IVR, chatbots): confusing navigation, "
        "limited functionality, inability to resolve complex issues; journey design overall.",
    "Retention & Loyalty":
        "(inferred) Keeping customers engaged after acquisition: follow-up, re-engagement, churn.",
    "Development capability": "(inferred) The ability to build and evolve products.",
    "Portfolio planning": "(inferred) How the range of offers is planned and structured.",
    "Awareness": "(inferred) Whether customers know the offers and services exist.",
    "Communication":
        "Ineffective communication that fails to engage customers or keep them informed about "
        "important updates, leading to dissatisfaction.",
    "Branding":
        "Weak or inconsistent branding that fails to convey the company's values and "
        "differentiators, impacting customer perception.",
    "Frontline operations":
        "Physical condition or availability of equipment and furniture that detracts from the "
        "customer's comfort and service experience at post-sales touchpoints.",
    "Self-service":
        "Inadequate or confusing provision for customers serving themselves, including signage "
        "and the absence of usable self-service paths.",
    "Call center": "Call-centre operations, capacity and organisation of service delivery.",
    "Staffing":
        "Inadequate staffing leading to overburdened employees, long wait times and declining "
        "service quality.",
    "HR Development":
        "Deficiencies in training and development that leave skill and knowledge gaps affecting "
        "service quality.",
    "Functionality":
        "Design and usability of digital platforms: poor layout, unintuitive navigation, lack of "
        "responsiveness.",
    "UI":
        "Frontend digital channels: broken links, incorrect routing, inability to upload "
        "documents, missing functionality.",
    "Backend":
        "Inadequate backend systems or lack of integration that slow service delivery or fail to "
        "support seamless interaction.",
    "Policies and guidelines":
        "(inferred) Missing, unclear or inconsistently applied rules, standards and guidelines.",
    "Backend operations":
        "(inferred) Internal and cross-functional operating processes, including manual, "
        "fragmented or undocumented ways of working.",
}

_LOWER = {d.lower(): d for d in TAXONOMY}
_SUB_LOWER = {s.lower(): (d, s) for d, subs in TAXONOMY.items() for s in subs}


def resolve(dimension: str | None, sub_category: str | None) -> tuple[str | None, str | None]:
    """Normalise a model-supplied (dimension, sub-category) pair to canonical labels.

    Returns (None, None) when the dimension is unrecognised, so a caller can drop the issue
    rather than file it under a guess. A recognised dimension with an unrecognised sub-category
    keeps the dimension and drops only the sub-category -- partial information is still useful.
    """
    dim = _LOWER.get((dimension or "").strip().lower())
    if dim is None:
        return None, None

    raw_sub = (sub_category or "").strip()
    if not raw_sub:
        return dim, None

    hit = _SUB_LOWER.get(raw_sub.lower())
    if hit and hit[0] == dim:
        return dim, hit[1]
    # Tolerate a sub-category given without its parent, as long as it is unambiguous.
    if hit:
        return hit[0], hit[1]
    return dim, None


def prompt_card() -> str:
    """The taxonomy WITH definitions, for a generation prompt.

    Labels alone are not enough: given only names, the model filed network outages under
    "Product" instead of "Systems and Technology". The definitions are what make the choice
    determinate.
    """
    blocks: list[str] = []
    for dim, subs in TAXONOMY.items():
        blocks.append(f"■ {dim}\n  {DIMENSION_DEFS.get(dim, '')}")
        for s in subs:
            blocks.append(f"   → {s}: {SUB_CATEGORY_DEFS.get(s, '')}")
        blocks.append("")
    return "\n".join(blocks).strip()
