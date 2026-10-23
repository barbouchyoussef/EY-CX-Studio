from __future__ import annotations

import re


_REPLACEMENTS = {
    "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢": "'",
    "ÃƒÂ¢Ã¢â€šÂ¬Ã‹Å“": "'",
    "ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ": '"',
    "ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â": '"',
    "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“": "-",
    "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â": "-",
    "ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦": "...",
    "Ãƒâ€š ": " ",
    "Ãƒâ€š": "",
    "ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢": "'",
    "ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¹Ã…â€œ": "'",
    "ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“": '"',
    "ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â": '"',
    "ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ": "-",
    "ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â": "-",
    "ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦": "...",
    "ÃƒÆ’Ã¢â‚¬Å¡ ": " ",
    "ÃƒÆ’Ã¢â‚¬Å¡": "",
    "â€™": "'",
    "â€˜": "'",
    "â€œ": '"',
    "â€": '"',
    "â€“": "-",
    "â€”": "-",
    "â€¢": "-",
    "â€¦": "...",
    "Â°": "°",
    "Â·": "·",
    "Â ": " ",
    "Â": "",
}

_MOJIBAKE_MARKERS = ("Ã", "Â", "â", "€", "™", "œ", "ž", "¢")


def _mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in _MOJIBAKE_MARKERS)


def _repair_mojibake(text: str) -> str:
    repaired = text
    for _ in range(3):
        if not any(marker in repaired for marker in _MOJIBAKE_MARKERS):
            break
        best = repaired
        for encoding in ("latin-1", "cp1252"):
            try:
                candidate = repaired.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if _mojibake_score(candidate) < _mojibake_score(best):
                best = candidate
        if best == repaired:
            break
        repaired = best
    return repaired


# The set of characters that a UTF-8 byte 0x80-0xFF becomes when decoded as CP1252 -- the
# fingerprint of "mojibake". CP1252 is used (not just Latin-1) because it also makes bytes
# 0x80-0x9F printable (€ ‰ œ – — " " · etc.), which is exactly the case Latin-1 missed: a
# 3-byte UTF-8 symbol whose middle byte lands in 0x80-0x9F (≤, –, ·, most smart punctuation)
# decodes to a char ABOVE U+00FF, so a [\x80-\xff]-only run split it and could not rebuild it.
_CP1252_HIGH = frozenset(
    ch for b in range(0x80, 0x100) for ch in bytes([b]).decode("cp1252", errors="ignore")
)


# Latin-1 mojibake produces the RAW code points U+0080-U+00FF, and the C1 block U+0080-U+009F is
# absent from the CP1252 set above -- CP1252 maps those byte values to printable punctuation
# instead, so the code points themselves never appear in it. They are exactly what a UTF-8
# continuation byte becomes when text was decoded as Latin-1, and they never occur in real prose,
# so they belong to a mojibake run too. Without them a run like "â" split after "â" and
# could not be rebuilt: the docstring claimed Latin-1 support the marker set did not have.
_LATIN1_C1 = frozenset(chr(b) for b in range(0x80, 0xA0))
_MOJIBAKE_RUN_CHARS = _CP1252_HIGH | _LATIN1_C1


def _fix_mojibake_runs(text: str) -> str:
    """Repair each maximal run of mojibake-high characters independently.

    Per-run (not whole-string) is what makes this safe on MIXED content: clean Arabic, a real €
    or curly quote elsewhere are left untouched, and a run that is not valid UTF-8 (a genuine
    Latin-1 accent like café) fails the decode and is kept as-is.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in _MOJIBAKE_RUN_CHARS:
            j = i
            while j < n and text[j] in _MOJIBAKE_RUN_CHARS:
                j += 1
            seg = text[i:j]
            # Which codec mangled it is not knowable from the result, so try both. CP1252 first
            # because it is the common case on Windows; Latin-1 catches the C1 runs CP1252
            # cannot even encode. A run that decodes as neither is genuine text (café) and is
            # left exactly as it was.
            for codec in ("cp1252", "latin-1"):
                try:
                    out.append(seg.encode(codec).decode("utf-8"))
                    break
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
            else:
                out.append(seg)
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def repair_encoding(text: str | None) -> str:
    """Repair UTF-8-decoded-as-CP1252/Latin-1 mojibake for ANY script (Latin, Arabic, ...).

    Fixes each run of high characters independently, so it recovers Arabic filenames
    (``Ø§ÙØ¬ÙØ¯Ø©`` → ``الجودة``), English punctuation (``Acmeâ€™s`` → ``Acme's``) and
    symbols mangled through CP1252 (``â‰¤`` → ``≤``, ``2022â€"2025`` → ``2022–2025``) alike,
    preserves structure (newlines, table pipes), and leaves clean text unchanged.
    """
    if not text:
        return text or ""
    out = text
    for _ in range(3):  # a couple of passes clears double-encoding
        repaired = _fix_mojibake_runs(out)
        if repaired == out:
            break
        out = repaired
    return out


def clean_optional_text(value: object) -> str | None:
    """`normalize_text` for a value that may be missing: empty comes back as None, not "".

    Accepts any type, because these values arrive from database columns and JSON payloads where a
    field can be absent, null, or not a string. Report schemas distinguish "no text" from "empty
    text", so the `or None` matters -- writing it out by hand a dozen times is how an empty string
    ends up rendered as a blank line in the report.
    """
    return normalize_text(str(value or "")) or None


def normalize_text(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    text = _repair_mojibake(text)
    for bad, good in _REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = re.sub(r"([A-Za-z])âs\b", r"\1's", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
