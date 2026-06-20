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


def get_model_router():
    """Import and return model router (deferred to avoid circular imports)."""
    from backend.routing.model_router import get_model_router as _get_router
    return _get_router()


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
        "severity_score": {
            "type": "number",
            "minimum": 1,
            "maximum": 10,
            "description": "Numeric severity score from 1-10 (1=lowest, 10=highest)"
        },
        "priority": {
            "type": "string",
            "enum": ["P0", "P1", "P2"],
            "description": "Priority level: P0 (Critical, severity 8-10), P1 (High, severity 5-7), P2 (Medium, severity 1-4)"
        },
        "complexity": {
            "type": "string",
            "enum": ["Low", "Medium", "High"],
            "description": "Implementation complexity to fix the violation"
        },
        "timeline": {
            "type": "string",
            "enum": ["Immediate", "Short-term", "Long-term"],
            "description": "Recommended timeline: Immediate (0-14 days), Short-term (15-30 days), Long-term (30-90 days)"
        },
        "article_violated": {
            "type": "string",
            "description": "Specific article or section violated (e.g., 'GDPR Article 22')"
        },
        "issue": {
            "type": "string",
            "description": "Clear, concise description of what the violation is and why it's problematic (1-2 sentences)"
        },
        "reasoning": {
            "type": "string",
            "description": "Detailed 3-5 sentence explanation covering: (1) What activity in the AI system triggers this article? (2) What does the regulation require? (3) How does the system fall short? (4) What are the potential consequences?"
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
        "engineering_scope": {
            "type": "string",
            "description": "Detailed engineering scope describing the technical work required"
        },
        "risk_factors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key risk factors if violation is not addressed"
        },
        "dependencies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Dependencies or prerequisites for implementing the fix"
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
        "severity_score",
        "priority",
        "complexity",
        "timeline",
        "article_violated",
        "issue",
        "reasoning",
        "evidence_quote",
        "remediation_steps",
        "engineering_scope",
        "risk_factors",
        "dependencies",
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
        model: str = None,
        api_key: Optional[str] = None,
        use_router: bool = True,
        use_caching: bool = True
    ):
        """
        Initialize the compliance judge.

        Args:
            framework: Regulatory framework (e.g., "GDPR", "SOX", "EU-AI").
            focus_area: Specific area of focus (e.g., "automated decision-making").
            model: Anthropic model to use. If None and use_router=True, uses ModelRouter.
            api_key: Anthropic API key.
            use_router: If True, use ModelRouter for intelligent model selection.
            use_caching: If True, use prompt caching to reduce costs (requires Claude 3.5+).
        """
        self.framework = framework
        self.focus_area = focus_area
        self.use_router = use_router
        self.use_caching = use_caching

        # Determine model to use
        if model:
            self.model = model
        elif use_router:
            router = get_model_router()
            self.model = router.get_model_for_framework(framework.lower())
            logger.info(f"ModelRouter selected {self.model} for {framework}")
        else:
            self.model = "claude-sonnet-4-6"

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        # Create Anthropic client with explicit proxy=None to avoid Render proxy issues
        import httpx
        http_client = httpx.Client(proxy=None)
        self._client = Anthropic(api_key=self.api_key, http_client=http_client)
        logger.info(f"Initialized {self.__class__.__name__} for {framework} - {focus_area} (caching: {use_caching})")

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

    def get_system_prompt(self) -> str:
        """
        Get the base system prompt for this judge.

        This can be overridden by subclasses to provide
        judge-specific instructions. Default provides generic
        compliance evaluation guidance.

        Returns:
            System prompt text.
        """
        return f"""You are an expert compliance judge specializing in {self.framework} regulations,
specifically focusing on {self.focus_area}.

Your role is to analyze AI system descriptions and policy documents to identify
compliance violations. Be thorough, precise, and cite specific regulatory requirements."""

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

        try:
            # Build prompt components
            if self.use_caching:
                # Use prompt caching: system blocks with cache_control
                system_prompt = self.get_system_prompt()
                regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

                # System blocks with caching
                system_blocks = [
                    {
                        "type": "text",
                        "text": system_prompt
                    },
                    {
                        "type": "text",
                        "text": f"# Regulatory Context\n\n{regulatory_context}",
                        "cache_control": {"type": "ephemeral"}  # Cache regulatory context
                    }
                ]

                # User message with submission
                user_prompt = f"""# AI System Description to Evaluate

{submission}

Analyze this AI system description against the regulatory context provided above.
Report any violations you detect."""

                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system=system_blocks,
                    messages=[{
                        "role": "user",
                        "content": user_prompt
                    }],
                    tools=[{
                        "name": "report_violation",
                        "description": "Report a compliance violation analysis result",
                        "input_schema": VIOLATION_SCHEMA
                    }],
                    tool_choice={"type": "tool", "name": "report_violation"}
                )

            else:
                # Traditional approach without caching
                prompt = self.build_prompt(submission, retrieved_chunks)
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

            # Record usage in ModelRouter if enabled
            if self.use_router:
                try:
                    router = get_model_router()
                    usage = response.usage
                    router.record_usage(
                        model=self.model,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens
                    )
                except Exception as e:
                    logger.warning(f"Failed to record usage in ModelRouter: {e}")

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

                    # Add abstention logic for low-confidence verdicts
                    confidence_score = result.get("confidence", 0)
                    if confidence_score < 0.65:
                        result["abstain"] = True
                        result["abstain_reason"] = "Insufficient evidence in policy or system description to confidently assess this violation. Recommend expert human review."
                    else:
                        result["abstain"] = False
                        result["abstain_reason"] = None

                    logger.info(
                        f"{self.judge_id}: Violation detected - "
                        f"{result.get('severity', 'UNKNOWN')} severity, "
                        f"confidence: {confidence_score:.2f}, abstain: {result.get('abstain', False)}"
                    )
                    return result

            logger.error("No tool use in response")
            return None

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            raise

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(framework='{self.framework}', focus='{self.focus_area}')"
