"""
Conflict Analyst agent — cross-regulation conflict detection.

Runs AFTER the synthesizer, only when 2+ frameworks were assessed and detected
findings span at least two of them. Surfaces genuine tensions where complying
with one regulation undermines compliance with another — the classic case being
GDPR Article 17 (right to erasure) vs SOX record-retention requirements.

Precision over recall (a fabricated conflict is worse than a missed one):
  - The model only ever sees the REAL detected findings, referenced by index.
  - Every surfaced conflict must reference two valid findings from two DIFFERENT
    frameworks; anything else is dropped server-side.
  - The emitted framework/clause references are DERIVED FROM the actual findings,
    not from model free-text — a conflict cannot cite a clause that wasn't
    detected.
  - On any parse/validation failure the analyst returns [] — it never fabricates.
"""
import os
import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError, field_validator

logger = logging.getLogger(__name__)

_LIKELIHOOD = {"HIGH", "MEDIUM", "LOW"}

CONFLICT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding_a_index": {
                        "type": "integer",
                        "description": "Index of the first finding (from the provided list) in tension."
                    },
                    "finding_b_index": {
                        "type": "integer",
                        "description": "Index of the second finding, which MUST be from a different framework."
                    },
                    "description": {
                        "type": "string",
                        "description": "Plain-language explanation of why satisfying one finding's remediation undermines the other's compliance."
                    },
                    "likelihood": {
                        "type": "string",
                        "enum": ["HIGH", "MEDIUM", "LOW"],
                        "description": "Likelihood this is a genuine, material conflict."
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence (0-1) that this conflict is real."
                    },
                    "reconciliation": {
                        "type": "string",
                        "description": "Concrete recommendation to reconcile the two requirements."
                    },
                    "requires_legal_review": {
                        "type": "boolean",
                        "description": "Whether resolving this tension needs qualified legal review."
                    }
                },
                "required": [
                    "finding_a_index", "finding_b_index", "description",
                    "likelihood", "confidence", "reconciliation", "requires_legal_review"
                ]
            }
        }
    },
    "required": ["conflicts"]
}

SYSTEM_PROMPT = """You are a cross-regulation compliance conflict analyst.

You are given a list of compliance findings that were ACTUALLY detected across
two or more regulatory frameworks. Your job is to identify GENUINE tensions:
cases where the remediation required by one finding would undermine compliance
with another finding from a DIFFERENT framework.

Strict rules:
- Only report a conflict when there is a real, material tension between two
  specific findings. The archetype is GDPR Article 17 (erase personal data on
  request) vs records-retention duties (retain records for a fixed period).
- Reference findings strictly by their [index] from the provided list.
- The two findings in a conflict MUST belong to different frameworks.
- Do NOT invent generic, hypothetical, or "could theoretically" conflicts. If
  the detected findings do not genuinely conflict, return an empty conflicts
  array. Precision matters far more than coverage here.
"""


class _Conflict(BaseModel):
    finding_a_index: int
    finding_b_index: int
    description: str
    likelihood: str
    confidence: float
    reconciliation: str
    requires_legal_review: bool

    @field_validator("likelihood", mode="before")
    @classmethod
    def _norm_likelihood(cls, v):
        s = str(v).strip().upper()
        return s if s in _LIKELIHOOD else "MEDIUM"

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5


class ConflictAnalystAgent:
    """Detects genuine cross-regulation conflicts grounded in real findings."""

    name = "conflict_analyst"

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        import httpx
        self._client = Anthropic(api_key=self.api_key, http_client=httpx.Client(proxy=None))
        self.model = model

    @staticmethod
    def _fw(v: Dict[str, Any]) -> str:
        return str(v.get("framework", "")).strip().upper()

    def analyze_conflicts(
        self,
        violations: List[Dict[str, Any]],
        frameworks: List[str],
    ) -> List[Dict[str, Any]]:
        """Return grounded cross-regulation conflicts, or [] when none/not applicable."""
        findings = [v for v in (violations or []) if v.get("violation_detected", True)]
        frameworks_present = {self._fw(v) for v in findings if self._fw(v)}

        # Gate: 2+ frameworks requested AND findings actually span 2+ frameworks.
        if len(frameworks or []) < 2 or len(frameworks_present) < 2 or len(findings) < 2:
            logger.info(
                "ConflictAnalyst: skipped (frameworks=%s, spanning=%s, findings=%d)",
                len(frameworks or []), len(frameworks_present), len(findings)
            )
            return []

        prompt = self._build_prompt(findings)
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                tools=[{
                    "name": "report_conflicts",
                    "description": "Report genuine cross-regulation conflicts between detected findings",
                    "input_schema": CONFLICT_TOOL_SCHEMA
                }],
                tool_choice={"type": "tool", "name": "report_conflicts"}
            )
        except Exception as e:
            logger.error(f"ConflictAnalyst LLM call failed: {e}")
            return []

        raw = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "report_conflicts":
                raw = block.input
                break
        if not raw:
            logger.warning("ConflictAnalyst: no tool output")
            return []

        conflicts_out: List[Dict[str, Any]] = []
        for c in (raw.get("conflicts") or []):
            try:
                cm = _Conflict.model_validate(c)
            except ValidationError as e:
                logger.warning(f"ConflictAnalyst: dropped malformed conflict: {e}")
                continue

            ai, bi = cm.finding_a_index, cm.finding_b_index
            # Guardrail: indices must be valid, distinct, and cross-framework.
            if not (0 <= ai < len(findings)) or not (0 <= bi < len(findings)) or ai == bi:
                logger.warning("ConflictAnalyst: dropped conflict with invalid/duplicate indices")
                continue
            fa, fb = findings[ai], findings[bi]
            if self._fw(fa) == self._fw(fb):
                logger.warning("ConflictAnalyst: dropped same-framework conflict")
                continue

            # References derived from the REAL findings, not model free-text.
            conflicts_out.append({
                "frameworks": [self._fw(fa), self._fw(fb)],
                "clauses": [fa.get("article_violated", ""), fb.get("article_violated", "")],
                "findings": [
                    {"framework": self._fw(fa), "clause": fa.get("article_violated", ""), "issue": fa.get("issue", "")},
                    {"framework": self._fw(fb), "clause": fb.get("article_violated", ""), "issue": fb.get("issue", "")},
                ],
                "description": cm.description,
                "likelihood": cm.likelihood,
                "confidence": round(cm.confidence, 3),
                "reconciliation": cm.reconciliation,
                "requires_legal_review": cm.requires_legal_review,
                "grounded": True,
            })

        logger.info(
            "ConflictAnalyst: %d grounded conflict(s) from %d findings across %d frameworks",
            len(conflicts_out), len(findings), len(frameworks_present)
        )
        return conflicts_out

    def _build_prompt(self, findings: List[Dict[str, Any]]) -> str:
        lines = ["# Detected compliance findings across multiple frameworks", ""]
        for i, v in enumerate(findings):
            clause = v.get("article_violated", "") or "(unspecified clause)"
            issue = v.get("issue", "") or v.get("reasoning", "") or ""
            lines.append(f"[{i}] ({self._fw(v)}) {clause}: {issue}")
            rem = v.get("remediation_steps", [])
            if isinstance(rem, list) and rem:
                lines.append(f"     Remediation requires: {'; '.join(str(s) for s in rem[:4])}")
        lines += [
            "",
            "Identify GENUINE cross-framework conflicts where one finding's required "
            "remediation would undermine compliance with another finding from a DIFFERENT "
            "framework. Reference findings by their [index]. Report only real, material "
            "tensions; return an empty array if there are none."
        ]
        return "\n".join(lines)
