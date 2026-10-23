"""Finding a JSON object inside a model's reply.

Models are asked for JSON and usually oblige, but they also prepend "Here is the report:", wrap
the object in a ```json fence, or add a closing remark. Rather than strip those cases one by one,
this scans for the first `{` that begins a valid object and decodes from there -- which handles
every wrapper at once, including ones nobody has seen yet.

Returns None when there is no object at all, so callers can say so plainly instead of raising.
"""

from __future__ import annotations

import json


def extract_json(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text or ""):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None
