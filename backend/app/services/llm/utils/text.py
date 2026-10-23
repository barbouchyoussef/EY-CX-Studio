"""Cleaning model output before it reaches a person.

Models format for a chat window: they quote the sentence they were asked for, bold what they think
matters, open lists with bullets. In a question rendered into the assessment UI or a summary
stored as memory, none of that is wanted -- it shows up as literal asterisks and stray dashes.

`clean_single_text` is for something meant to be one line, such as a question. `clean_memory_text`
keeps line structure but caps the result, because axis memory has to stay compact to be useful.
"""

from __future__ import annotations

import re

from app.core.text_normalization import normalize_text


def clean_single_text(text: str | None) -> str:
    value = normalize_text(text)
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        value = value[1:-1].strip()
    value = value.replace("**", "").replace("__", "")
    value = re.sub(r"(?<!\w)[*_](?!\s)|(?<!\s)[*_](?!\w)", "", value)
    value = re.sub(r"(^|\s)[-•]\s+", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_memory_text(text: str | None) -> str:
    value = normalize_text(text)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"^```[a-zA-Z]*\n?", "", value).strip()
    value = re.sub(r"\n?```$", "", value).strip()
    lines = [line.strip() for line in value.split("\n") if line.strip()]
    return "\n".join(lines[:8]).strip()
