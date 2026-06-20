"""
Coercion helpers for normalizing LLM tool-call output into clean lists.

Some judge responses return list-typed fields such as ``remediation_steps`` /
``risk_factors`` / ``dependencies`` as a single raw string (occasionally
containing tool-call XML scaffolding like ``<parameter name="0">...``) instead
of a JSON array of strings. These helpers normalize such values into a clean
``list[str]`` so both the web UI and the PDF report render each item as a full
sentence rather than iterating a string character-by-character.
"""
import re
from typing import Any, List

_TAG_RE = re.compile(r"<[^>]+>")
_LEADING_MARKER_RE = re.compile(r"^\s*(?:\d+[\.\)]|[-•*])\s+")


def _split_string_to_items(text: str) -> List[str]:
    """Split a single string into discrete, cleaned items.

    Handles tool-call XML scaffolding (``<parameter name="N">...</parameter>``)
    as well as plain newline- or number-delimited text.
    """
    text = text.strip()
    if not text:
        return []
    if "<" in text and ">" in text:
        # Tool-call XML scaffolding: split on tag boundaries.
        raw_parts = _TAG_RE.split(text)
    else:
        # Plain string: split on newlines or numbered markers ("1. ", "2) ").
        raw_parts = re.split(r"\n+|(?<!\w)\d+[\.\)]\s+", text)
    items: List[str] = []
    for part in raw_parts:
        cleaned = _LEADING_MARKER_RE.sub("", _TAG_RE.sub("", part).strip()).strip()
        if cleaned:
            items.append(cleaned)
    return items


def coerce_str_list(value: Any) -> List[str]:
    """Normalize a value into a clean ``list[str]``, dropping empties.

    - ``list``  -> clean each item; if an item is itself a malformed
                   XML-scaffold string, split it into discrete items.
    - ``str``   -> strip XML tags and split into discrete items.
    - other     -> single-item list (stringified) or ``[]`` if empty.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return _split_string_to_items(value)
    if isinstance(value, list):
        items: List[str] = []
        for entry in value:
            if isinstance(entry, str) and "<" in entry and ">" in entry:
                items.extend(_split_string_to_items(entry))
            elif entry is not None:
                s = str(entry).strip()
                if s:
                    items.append(s)
        return items
    s = str(value).strip()
    return [s] if s else []
