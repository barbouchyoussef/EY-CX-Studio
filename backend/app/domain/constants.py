AXES_ORDER = ["Manage", "Analyze", "Improve"]

_AXIS_NAME_ALIASES = {
    "manage": "Manage",
    "analyze": "Analyze",
    "improve": "Improve",
    "maintain": "Improve",
}

_AXIS_CODE_ALIASES = {
    "manage": "MANAGE",
    "analyze": "ANALYZE",
    "improve": "IMPROVE",
    "maintain": "IMPROVE",
}


def normalize_axis_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _AXIS_NAME_ALIASES.get(value.strip().lower())
    return normalized or value.strip()


def normalize_axis_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _AXIS_CODE_ALIASES.get(value.strip().lower())
    return normalized or value.strip().upper()


def axis_name_variants(value: str | None) -> list[str]:
    if value is None:
        return []
    raw = value.strip().lower()
    if raw in {"improve", "maintain"}:
        return ["improve", "maintain"]
    return [raw]

ASSESSMENT_STATUS_IN_PROGRESS = "active"
ASSESSMENT_STATUS_COMPLETED = "completed"
