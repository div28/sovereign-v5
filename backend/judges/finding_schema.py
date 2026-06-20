"""
Strict validation for compliance-judge tool output.

Judges return their finding via the ``report_violation`` tool. The model
occasionally emits off-schema shapes (e.g. ``remediation_steps`` as a single
raw string containing tool-call XML scaffolding). ``JudgeFinding`` validates
and normalizes that output before it is stored or returned, so malformed data
never reaches the UI or PDF.

Field names match the existing ``report_violation`` schema, so the API
response shape the frontend and PDF depend on is unchanged. Extra keys
(``judge_id``, ``framework``, ``focus_area``, ``priority``, ``complexity``,
``timeline``, ``engineering_scope``, ...) are preserved via ``extra="allow"``.
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from backend.utils.list_coercion import coerce_str_list

_VALID_SEVERITY = {"CRITICAL", "MAJOR", "MINOR", "NONE"}


class JudgeSchemaError(Exception):
    """Raised when a judge's output fails schema validation after a retry."""


class JudgeFinding(BaseModel):
    """Validated, normalized structure for a single judge finding."""

    # Preserve metadata and PDF-only fields not modeled explicitly below.
    model_config = ConfigDict(extra="allow")

    violation_detected: bool
    severity: str
    article_violated: str
    issue: str
    reasoning: str
    evidence_quote: str
    remediation_steps: List[str]
    risk_factors: List[str]
    dependencies: List[str] = []
    confidence: float
    severity_score: Optional[float] = None

    @field_validator("remediation_steps", "risk_factors", "dependencies", mode="before")
    @classmethod
    def _coerce_lists(cls, value):
        # Strip XML scaffolding and split a stray single string into a clean list.
        return coerce_str_list(value)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, value):
        normalized = str(value).strip().upper()
        if normalized not in _VALID_SEVERITY:
            raise ValueError(
                f"severity must be one of {sorted(_VALID_SEVERITY)}, got {value!r}"
            )
        return normalized

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value):
        return max(0.0, min(1.0, float(value)))

    @field_validator("severity_score", mode="before")
    @classmethod
    def _clamp_severity_score(cls, value):
        if value is None:
            return None
        return max(1.0, min(10.0, float(value)))
