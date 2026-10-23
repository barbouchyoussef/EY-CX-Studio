AXIS_CONSULTANT_GUIDANCE = (
    "- Interpret the axis name and missing capability labels semantically.\n"
    "- Translate abstract CX concepts into practical business language a non-technical leader can answer.\n"
    "- Ask about one practical signal at a time: owner, cadence, tool, action, or metric."
)

STAGE_DISCOVERY_GUIDANCE_BY_STAGE = {
    "intro": (
        "- Start with one simple question around {focus}.\n"
        "- Ask for current practice, not proof."
    ),
    "diagnostic": (
        "- Ask one useful maturity signal around {focus}: owner, cadence, tool, follow-up, or outcome."
    ),
    "deep_dive": (
        "- Ask one last simple detail around {focus} only if ambiguity remains."
    ),
}


def stage_discovery_guidance(conversation_stage: str, focus: str) -> str:
    template = STAGE_DISCOVERY_GUIDANCE_BY_STAGE.get(
        conversation_stage,
        STAGE_DISCOVERY_GUIDANCE_BY_STAGE["deep_dive"],
    )
    return template.format(focus=focus)
