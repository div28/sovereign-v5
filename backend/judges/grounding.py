"""
Grounding / traceability checks for compliance-judge findings.

For an audit artifact, every finding must be traceable, not just asserted:

  - Input grounding: ``evidence_quote`` is a verbatim span copied from the
    submission, so a reader can locate exactly what triggered the finding.
  - Regulatory grounding: ``article_violated`` maps to a real retrieved RAG
    chunk (source doc + chunk id), so the citation traces to the corpus rather
    than being fabricated by the model.

CRITICAL: these checks NEVER drop, suppress, or alter a detected violation.
They only attach grounding flags plus a traceable clause pointer so the finding
can be verified. A finding that does not fully ground is FLAGGED, not removed.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

# Match "Article 22", "Art. 17", "Section 404", "Sec 302", "§ 9" (leading zeros ok).
_CLAUSE_RE = re.compile(r"\b(article|art\.?|section|sec\.?|§)\s*0*([0-9]+)([a-z])?", re.IGNORECASE)

# Smart quotes / dashes -> ASCII, so a verbatim span isn't flagged over typography.
_QUOTE_MAP = {
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "–": "-", "—": "-",
}


def _normalize_text(s: str) -> str:
    """Lowercase, unify smart quotes/dashes, and collapse whitespace."""
    for fancy, plain in _QUOTE_MAP.items():
        s = s.replace(fancy, plain)
    return re.sub(r"\s+", " ", s).strip().casefold()


def _clause_type(token: str) -> str:
    t = token.lower().rstrip(".")
    if t.startswith("sec"):
        return "section"
    return "article"  # article / art / § all normalize to article


def _clause_keys(text: str) -> set:
    """Set of (type, number) clause keys in a string, e.g. {('article', '22')}."""
    keys = set()
    for m in _CLAUSE_RE.finditer(text or ""):
        number = (m.group(2) + (m.group(3) or "")).lower()
        keys.add((_clause_type(m.group(1)), number))
    return keys


def check_evidence_grounding(evidence_quote: str, submission: str) -> Tuple[bool, str]:
    """Return (grounded, match_kind) for evidence_quote against the submission.

    match_kind is "exact" | "normalized" | "not_found". A normalized match
    (whitespace/smart-quote differences only) still counts as grounded.
    """
    if not evidence_quote or not evidence_quote.strip():
        return False, "not_found"
    if evidence_quote in (submission or ""):
        return True, "exact"
    norm_quote = _normalize_text(evidence_quote)
    if norm_quote and norm_quote in _normalize_text(submission or ""):
        return True, "normalized"
    return False, "not_found"


def match_clause(
    article_violated: str,
    retrieved_chunks: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Find the retrieved chunk the cited clause maps to.

    Returns a traceable clause_source pointer (chunk id + source doc + clause
    metadata), or None if no retrieved chunk corresponds to the cited clause.
    Prefers a metadata match; falls back to a chunk whose text references the
    clause.
    """
    cited = _clause_keys(article_violated)
    if not cited:
        return None

    text_fallback = None
    for chunk in retrieved_chunks or []:
        md = chunk.get("metadata", {}) or {}
        source = {
            "chunk_id": chunk.get("id", ""),
            "source": md.get("source", "") or md.get("title", ""),
            "article": md.get("article", ""),
            "section": md.get("section", ""),
            "page": md.get("page", ""),
            "score": chunk.get("score", None),
        }
        # Strong match: clause type+number present in the chunk's metadata.
        metadata_keys = _clause_keys(f"{md.get('article', '')} {md.get('section', '')}")
        if cited & metadata_keys:
            source["match"] = "metadata"
            return source
        # Weak fallback: the chunk text references the cited clause.
        if text_fallback is None and (cited & _clause_keys(chunk.get("text", ""))):
            source["match"] = "text"
            text_fallback = source
    return text_fallback


def ground_finding(
    result: Dict[str, Any],
    submission: str,
    retrieved_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Attach grounding flags + a traceable clause pointer to a finding.

    Flag-only: this NEVER drops, suppresses, or alters the violation itself.
    Adds: evidence_grounded, evidence_match, clause_grounded, clause_source,
    grounded, grounding_confidence.
    """
    evidence_grounded, evidence_match = check_evidence_grounding(
        result.get("evidence_quote", ""), submission
    )
    clause_source = match_clause(result.get("article_violated", ""), retrieved_chunks)
    clause_grounded = clause_source is not None

    evidence_component = {"exact": 1.0, "normalized": 0.7, "not_found": 0.0}[evidence_match]
    if clause_source and clause_source.get("match") == "metadata":
        clause_component = 1.0
    elif clause_grounded:
        clause_component = 0.7
    else:
        clause_component = 0.0

    result["evidence_grounded"] = evidence_grounded
    result["evidence_match"] = evidence_match
    result["clause_grounded"] = clause_grounded
    result["clause_source"] = clause_source
    result["grounded"] = bool(evidence_grounded and clause_grounded)
    result["grounding_confidence"] = round(0.5 * evidence_component + 0.5 * clause_component, 3)
    return result
