"""
Base Compliance Judge for Sovereign V5

Abstract base class for all regulatory compliance judges.
Uses Anthropic structured outputs for consistent violation reporting.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from enum import Enum

from anthropic import Anthropic

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Violation severity levels."""
    CRITICAL = "CRITICAL"  # Immediate legal/regulatory risk
    MAJOR = "MAJOR"        # Significant compliance gap
    MINOR = "MINOR"        # Minor improvement needed
    NONE = "NONE"          # No violation detected


# JSON Schema for structured violation output
VIOLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "violation_detected": {
            "type": "boolean",
            "description": "Whether a violation was detected"
        },
        "severity": {
            "type": "string",
            "enum": ["CRITICAL", "MAJOR", "MINOR", "NONE"],
            "description": "Severity level of the violation"
        },
        "article_violated": {
            "type": "string",
            "description": "Specific article or section violated (e.g., 'GDPR Article 22')"
        },
        "evidence_quote": {
            "type": "string",
            "description": "Direct quote from submission showing the violation"
        },
        "remediation_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific steps to remediate the violation"
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Confidence score between 0 and 1"
        }
    },
    "required": [
        "violation_detected",
        "severity",
        "article_violated",
        "evidence_quote",
        "remediation_steps",
        "confidence"
    ]
}


class BaseComplianceJudge(ABC):
    """
    Abstract base class for compliance judges.

    Each judge specializes in detecting specific types of violations
    within a regulatory framework (e.g., GDPR Article 22 violations).
    """

    def __init__(
        self,
        framework: str,
        focus_area: str,
        model: str = "claude-3-5-haiku-20241022",
        api_key: Optional[str] = None
    ):
        """
        Initialize the compliance judge.

        Args:
            framework: Regulatory framework (e.g., "GDPR", "SOX", "EU-AI").
            focus_area: Specific area of focus (e.g., "automated decision-making").
            model: Anthropic model to use for evaluation.
            api_key: Anthropic API key.
        """
        self.framework = framework
        self.focus_area = focus_area
        self.model = model

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        self._client = Anthropic(api_key=self.api_key)
        logger.info(f"Initialized {self.__class__.__name__} for {framework} - {focus_area}")

    @property
    def judge_id(self) -> str:
        """Unique identifier for this judge."""
        return f"{self.framework.lower()}_{self.focus_area.replace(' ', '_').lower()}"

    @abstractmethod
    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Build the evaluation prompt for this judge.

        Args:
            submission: Text to evaluate for compliance.
            retrieved_chunks: Relevant regulatory context from RAG.

        Returns:
            Complete prompt for the LLM evaluation.
        """
        pass

    def _format_chunks_for_prompt(
        self,
        chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Format retrieved chunks for inclusion in prompt.

        Args:
            chunks: List of retrieved document chunks.

        Returns:
            Formatted string of regulatory context.
        """
        if not chunks:
            return "No specific regulatory context retrieved."

        formatted = []
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            article = metadata.get("article", "Unknown")
            section = metadata.get("section", "")

            header = f"[{article}]" if article else f"[Source {i}]"
            if section:
                header += f" {section}"

            formatted.append(f"{header}\n{text}")

        return "\n\n---\n\n".join(formatted)

    def evaluate(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a submission for compliance violations.

        Uses Anthropic structured outputs to ensure consistent
        violation reporting format.

        Args:
            submission: Text to evaluate.
            retrieved_chunks: Relevant regulatory context.

        Returns:
            Violation dict if detected, None if no violation.
        """
        if not submission or not submission.strip():
            logger.warning("Empty submission provided")
            return None

        # Build the evaluation prompt
        prompt = self.build_prompt(submission, retrieved_chunks)

        try:
            # Use structured output with JSON schema
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                tools=[{
                    "name": "report_violation",
                    "description": "Report a compliance violation analysis result",
                    "input_schema": VIOLATION_SCHEMA
                }],
                tool_choice={"type": "tool", "name": "report_violation"}
            )

            # Extract structured result from tool use
            for block in response.content:
                if block.type == "tool_use" and block.name == "report_violation":
                    result = block.input

                    # Add metadata
                    result["judge_id"] = self.judge_id
                    result["framework"] = self.framework
                    result["focus_area"] = self.focus_area

                    # Return None if no violation detected
                    if not result.get("violation_detected", False):
                        logger.info(f"{self.judge_id}: No violation detected")
                        return None

                    logger.info(
                        f"{self.judge_id}: Violation detected - "
                        f"{result.get('severity', 'UNKNOWN')} severity"
                    )
                    return result

            logger.error("No tool use in response")
            return None

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            raise

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(framework='{self.framework}', focus='{self.focus_area}')"
