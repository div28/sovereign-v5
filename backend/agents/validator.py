"""
Validator Agent for Sovereign V5 Multi-Agent System

Base class for compliance validator agents (judges). Each validator
specializes in detecting violations for specific regulatory articles.

Validators can:
- Plan their evaluation strategy
- Execute compliance checks
- Reflect on confidence and request more context
- Flag low-confidence findings for re-evaluation
"""

import os
import asyncio
import logging
import time
from abc import abstractmethod
from typing import Dict, List, Any, Optional

from anthropic import Anthropic

from .base_agent import Agent, AgentPlan, AgentResult, Reflection, CONFIDENCE_THRESHOLD
from .shared_memory import SharedMemory

logger = logging.getLogger(__name__)


class ValidatorAgent(Agent):
    """
    Base Validator Agent for compliance evaluation.

    Extends the Agent base class with compliance-specific functionality.
    Each concrete validator (GDPR Article 22, SOX Section 404, etc.)
    inherits from this class.

    Responsibilities:
        - Evaluate AI system descriptions against regulatory requirements
        - Detect violations with confidence scoring
        - Request additional context when uncertain
        - Flag low-confidence findings for orchestrator review

    Tools:
        - request_more_context: Ask Researcher for additional info
        - flag_low_confidence: Mark finding for re-evaluation
        - escalate_to_human: Request human review for edge cases
    """

    TOOLS = [
        "request_more_context",
        "flag_low_confidence",
        "escalate_to_human"
    ]

    def __init__(
        self,
        name: str,
        framework: str,
        focus_area: str,
        scratchpad: Optional[SharedMemory] = None,
        model: str = "claude-3-5-haiku-20241022",
        confidence_threshold: Optional[float] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the Validator Agent.

        Args:
            name: Unique identifier (e.g., "gdpr_article_22").
            framework: Regulatory framework (GDPR, SOX, EUAI).
            focus_area: Specific focus (e.g., "automated decision-making").
            scratchpad: SharedMemory for inter-agent communication.
            model: Claude model to use.
            confidence_threshold: Minimum confidence for acceptance.
            api_key: Anthropic API key.
        """
        super().__init__(
            name=name,
            tools=self.TOOLS,
            scratchpad=scratchpad,
            confidence_threshold=confidence_threshold,
            max_iterations=2  # Validators may retry once with more context
        )

        self.framework = framework
        self.focus_area = focus_area
        self.model = model

        # API client setup
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        import httpx
        http_client = httpx.Client(proxy=None)
        self._client = Anthropic(api_key=self.api_key, http_client=http_client)

        logger.info(f"ValidatorAgent '{name}' initialized for {framework} - {focus_area}")

    @property
    def judge_id(self) -> str:
        """Compatibility with existing judge interface."""
        return self.name

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this validator.

        Must be implemented by concrete validators.
        """
        pass

    @abstractmethod
    def get_evaluation_prompt(self) -> str:
        """
        Get the evaluation prompt template for this validator.

        Must be implemented by concrete validators.
        """
        pass

    def _format_chunks_for_prompt(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks for inclusion in prompt."""
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

    async def plan(self, goal: str, context: Dict[str, Any]) -> AgentPlan:
        """
        Plan the evaluation strategy.

        Analyzes the submission and context to determine:
        - What aspects to focus on
        - What regulatory requirements apply
        - Whether there's enough context
        """
        submission = context.get("submission", "")
        chunks = context.get("chunks", [])
        is_retry = context.get("is_retry", False)
        previous_result = context.get("previous_result", {})

        # Determine strategy
        if is_retry:
            steps = [
                "Re-evaluate with additional context",
                f"Focus on previously uncertain areas: {previous_result.get('uncertain_areas', [])}",
                "Update confidence assessment"
            ]
            complexity = "medium"
        else:
            steps = [
                f"Evaluate submission against {self.framework} {self.focus_area}",
                "Check safe conditions first",
                "Identify any violations",
                "Assess confidence level"
            ]
            complexity = "medium" if len(chunks) > 5 else "low"

        return AgentPlan(
            agent_name=self.name,
            goal=goal,
            steps=steps,
            tools_to_use=["evaluate"],
            estimated_complexity=complexity,
            context_needed=[],
            metadata={
                "submission": submission,
                "chunks": chunks,
                "is_retry": is_retry,
                "chunks_count": len(chunks)
            }
        )

    async def act(self, plan: AgentPlan) -> AgentResult:
        """
        Execute the compliance evaluation.

        Uses the existing judge evaluation pattern with Claude tool_use.
        """
        start_time = time.time()
        metadata = plan.metadata
        submission = metadata.get("submission", "")
        chunks = metadata.get("chunks", [])

        if not submission or not submission.strip():
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={},
                confidence=0.0,
                errors=["Empty submission provided"]
            )

        try:
            # Build prompt components
            system_prompt = self.get_system_prompt()
            regulatory_context = self._format_chunks_for_prompt(chunks)

            # System blocks with caching for regulatory context
            system_blocks = [
                {
                    "type": "text",
                    "text": system_prompt
                },
                {
                    "type": "text",
                    "text": f"# Regulatory Context\n\n{regulatory_context}",
                    "cache_control": {"type": "ephemeral"}
                }
            ]

            # User message
            user_prompt = f"""# AI System Description to Evaluate

{submission}

Analyze this AI system description against the regulatory context provided above.
Report any violations you detect."""

            # Call Claude with tool_use
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_blocks,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[{
                    "name": "report_violation",
                    "description": "Report a compliance violation analysis result",
                    "input_schema": self._get_violation_schema()
                }],
                tool_choice={"type": "tool", "name": "report_violation"}
            )

            execution_time = (time.time() - start_time) * 1000

            # Record LLM usage
            if self.scratchpad:
                self.scratchpad.record_llm_call(
                    response.usage.input_tokens,
                    response.usage.output_tokens
                )

            # Extract result from tool use
            result = None
            for block in response.content:
                if block.type == "tool_use" and block.name == "report_violation":
                    result = block.input
                    break

            if not result:
                return AgentResult(
                    agent_name=self.name,
                    success=False,
                    data={},
                    confidence=0.0,
                    execution_time_ms=execution_time,
                    errors=["No tool use in response"]
                )

            # Add metadata
            result["judge_id"] = self.name
            result["framework"] = self.framework
            result["focus_area"] = self.focus_area

            # Get confidence
            confidence = result.get("confidence", 0.5)

            # Log reasoning to scratchpad
            if self.scratchpad:
                self.scratchpad.set_judge_reasoning(self.name, {
                    "violation_detected": result.get("violation_detected", False),
                    "severity": result.get("severity", "NONE"),
                    "confidence": confidence,
                    "article_violated": result.get("article_violated", ""),
                    "reasoning": result.get("reasoning", ""),
                    "execution_time_ms": execution_time
                })

            logger.info(
                f"Validator '{self.name}': violation={result.get('violation_detected')}, "
                f"confidence={confidence:.2f}, time={execution_time:.0f}ms"
            )

            return AgentResult(
                agent_name=self.name,
                success=True,
                data=result,
                confidence=confidence,
                execution_time_ms=execution_time,
                tools_used=["report_violation"]
            )

        except Exception as e:
            logger.error(f"Validator '{self.name}' action failed: {e}")
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={},
                confidence=0.0,
                execution_time_ms=(time.time() - start_time) * 1000,
                errors=[str(e)]
            )

    async def reflect(self, result: AgentResult) -> Reflection:
        """
        Reflect on the evaluation result.

        Checks confidence and determines if retry with more context is needed.
        """
        confidence = result.confidence
        violation_detected = result.data.get("violation_detected", False)

        # Check if we need to flag low confidence
        if confidence < self.confidence_threshold:
            # Determine what context might help
            context_needed = []

            if violation_detected:
                article = result.data.get("article_violated", "")
                if article:
                    context_needed.append(f"enforcement cases for {article}")
                    context_needed.append(f"specific requirements for {article}")

            # Flag in scratchpad
            if self.scratchpad:
                self.scratchpad.flag_low_confidence(
                    judge_id=self.name,
                    confidence=confidence,
                    reason=f"Confidence {confidence:.2f} below threshold {self.confidence_threshold}",
                    context_needed=context_needed
                )

            return Reflection(
                agent_name=self.name,
                confidence=confidence,
                needs_retry=self._iteration_count < self.max_iterations,
                reasoning=f"Low confidence ({confidence:.2f}) in evaluation. "
                         f"{'Will retry with more context.' if self._iteration_count < self.max_iterations else 'Max retries reached.'}",
                gaps_identified=[f"Uncertainty in {self.focus_area} assessment"],
                context_needed=context_needed,
                iteration=self._iteration_count
            )

        # High confidence result
        return Reflection(
            agent_name=self.name,
            confidence=confidence,
            needs_retry=False,
            reasoning=f"Confident evaluation: "
                     f"{'Violation detected' if violation_detected else 'No violation'} "
                     f"with {confidence:.2f} confidence",
            iteration=self._iteration_count
        )

    def _get_violation_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for violation reporting."""
        return {
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
                    "description": "Numeric severity score from 1-10"
                },
                "priority": {
                    "type": "string",
                    "enum": ["P0", "P1", "P2"],
                    "description": "Priority level: P0 (Critical), P1 (High), P2 (Medium)"
                },
                "complexity": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High"],
                    "description": "Implementation complexity to fix"
                },
                "timeline": {
                    "type": "string",
                    "enum": ["Immediate", "Short-term", "Long-term"],
                    "description": "Recommended remediation timeline"
                },
                "article_violated": {
                    "type": "string",
                    "description": "Specific article or section violated"
                },
                "issue": {
                    "type": "string",
                    "description": "Brief description of the violation"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Detailed explanation of the assessment"
                },
                "evidence_quote": {
                    "type": "string",
                    "description": "Direct quote from submission showing the violation"
                },
                "remediation_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Steps to remediate the violation"
                },
                "engineering_scope": {
                    "type": "string",
                    "description": "Technical work required"
                },
                "risk_factors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key risk factors if not addressed"
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Prerequisites for implementing the fix"
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

    # =========================================================================
    # COMPATIBILITY METHODS (for use with existing judge interface)
    # =========================================================================

    def evaluate(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous evaluate method for backwards compatibility.

        Wraps the async agent pattern for use with existing code.
        """
        import asyncio

        async def _evaluate():
            context = {
                "submission": submission,
                "chunks": retrieved_chunks
            }
            result = await self.run(
                f"Evaluate for {self.framework} {self.focus_area} compliance",
                context
            )

            if result.success and result.data.get("violation_detected"):
                return result.data
            return None

        # Run async in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context, use run_coroutine_threadsafe
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(_evaluate(), loop)
                return future.result(timeout=30)
            else:
                return loop.run_until_complete(_evaluate())
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(_evaluate())


class GDPRValidatorAgent(ValidatorAgent):
    """Base validator for GDPR-related compliance checks."""

    def __init__(
        self,
        name: str,
        focus_area: str,
        scratchpad: Optional[SharedMemory] = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            framework="GDPR",
            focus_area=focus_area,
            scratchpad=scratchpad,
            **kwargs
        )


class SOXValidatorAgent(ValidatorAgent):
    """Base validator for SOX-related compliance checks."""

    def __init__(
        self,
        name: str,
        focus_area: str,
        scratchpad: Optional[SharedMemory] = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            framework="SOX",
            focus_area=focus_area,
            scratchpad=scratchpad,
            **kwargs
        )


class EUAIValidatorAgent(ValidatorAgent):
    """Base validator for EU AI Act-related compliance checks."""

    def __init__(
        self,
        name: str,
        focus_area: str,
        scratchpad: Optional[SharedMemory] = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            framework="EUAI",
            focus_area=focus_area,
            scratchpad=scratchpad,
            **kwargs
        )
