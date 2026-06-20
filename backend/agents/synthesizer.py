"""
Synthesis Agent for Sovereign V5 Multi-Agent System

Transforms raw violations into coherent compliance reports with:
- Executive summary (narrative prose, not bullets)
- Prioritized findings by business impact
- Remediation roadmap with effort estimates
- Confidence improvement analysis
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional

from anthropic import Anthropic

from .base_agent import Agent, AgentPlan, AgentResult, Reflection
from .shared_memory import SharedMemory

logger = logging.getLogger(__name__)


class SynthesisAgent(Agent):
    """
    Synthesis Agent that generates coherent compliance reports.

    Responsibilities:
        - Read all violations and judge reasoning from scratchpad
        - Generate executive summary in narrative prose
        - Prioritize findings by business impact and enforcement likelihood
        - Create actionable remediation roadmap
        - Analyze how reflection loop improved confidence

    Tools:
        - generate_executive_summary: Create narrative summary
        - prioritize_findings: Sort by business impact
        - format_remediation: Create actionable roadmap
        - generate_pdf: Export to PDF (calls existing generator)
    """

    TOOLS = [
        "generate_executive_summary",
        "prioritize_findings",
        "format_remediation",
        "generate_pdf"
    ]

    SYNTHESIS_PROMPT = """You are an expert compliance analyst writing an executive summary for C-level executives.

Based on the following compliance assessment results, write a professional executive summary.

## Assessment Overview
- Frameworks Analyzed: {frameworks}
- Total Violations Found: {violation_count}
- Risk Score: {risk_score}/100
- Assessment Iterations: {iterations}

## Violations by Severity
{severity_breakdown}

## Key Findings
{key_findings}

## Judge Reasoning Summary
{reasoning_summary}

## Instructions
Write a concise executive summary (2-3 paragraphs) that:
1. States the overall compliance status clearly
2. Highlights the most critical findings and their business impact
3. Provides a high-level remediation recommendation
4. Notes any areas of uncertainty that require human review

IMPORTANT:
- Write in professional narrative prose (NOT bullet points)
- Focus on business impact, not technical details
- Be direct about risks without being alarmist
- If confidence was improved through iteration, mention this briefly
"""

    def __init__(
        self,
        scratchpad: Optional[SharedMemory] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the Synthesis Agent.

        Args:
            scratchpad: SharedMemory for reading judge outputs.
            api_key: Anthropic API key.
        """
        super().__init__(
            name="synthesizer",
            tools=self.TOOLS,
            scratchpad=scratchpad,
            max_iterations=1  # Synthesis doesn't need iteration
        )

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        import httpx
        http_client = httpx.Client(proxy=None)
        self._client = Anthropic(api_key=self.api_key, http_client=http_client)
        self.model = "claude-haiku-4-5"

        logger.info("SynthesisAgent initialized")

    async def plan(self, goal: str, context: Dict[str, Any]) -> AgentPlan:
        """
        Plan synthesis approach based on findings.
        """
        violations = context.get("violations", [])
        frameworks = context.get("frameworks", [])

        # Determine complexity based on findings
        if len(violations) == 0:
            complexity = "low"
            steps = ["Generate clean compliance summary"]
        elif len(violations) <= 3:
            complexity = "medium"
            steps = [
                "Generate executive summary",
                "Prioritize findings",
                "Create remediation roadmap"
            ]
        else:
            complexity = "high"
            steps = [
                "Analyze severity distribution",
                "Generate executive summary",
                "Prioritize by business impact",
                "Create detailed remediation roadmap",
                "Calculate confidence improvements"
            ]

        return AgentPlan(
            agent_name=self.name,
            goal=goal,
            steps=steps,
            tools_to_use=self.TOOLS,
            estimated_complexity=complexity,
            metadata={
                "violations": violations,
                "frameworks": frameworks,
                "violation_count": len(violations)
            }
        )

    async def act(self, plan: AgentPlan) -> AgentResult:
        """
        Generate synthesis components.
        """
        start_time = time.time()
        violations = plan.metadata.get("violations", [])
        frameworks = plan.metadata.get("frameworks", [])

        try:
            # Get judge reasoning from scratchpad
            judge_reasoning = {}
            iterations = 1
            if self.scratchpad:
                judge_reasoning = self.scratchpad.get_judge_reasoning()
                iterations = self.scratchpad.get_current_iteration() or 1

            # Calculate risk score
            risk_score = self._calculate_risk_score(violations)

            # Generate executive summary
            executive_summary = await self._generate_executive_summary(
                violations=violations,
                frameworks=frameworks,
                risk_score=risk_score,
                iterations=iterations,
                judge_reasoning=judge_reasoning
            )

            # Prioritize findings
            prioritized = self._prioritize_by_impact(violations)

            # Generate remediation roadmap
            remediation = self._generate_remediation_roadmap(prioritized)

            # Calculate confidence improvements
            confidence_improvements = self._calculate_confidence_improvements()

            execution_time = (time.time() - start_time) * 1000

            result_data = {
                "executive_summary": executive_summary,
                "prioritized_findings": prioritized,
                "remediation_roadmap": remediation,
                "confidence_improvements": confidence_improvements,
                "risk_score": risk_score,
                "severity_breakdown": self._count_severities(violations)
            }

            logger.info(f"Synthesis complete in {execution_time:.0f}ms")

            return AgentResult(
                agent_name=self.name,
                success=True,
                data=result_data,
                confidence=0.95,  # Synthesis is deterministic
                execution_time_ms=execution_time,
                tools_used=["generate_executive_summary", "prioritize_findings", "format_remediation"]
            )

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={
                    "executive_summary": "Unable to generate summary due to an error.",
                    "prioritized_findings": violations,
                    "remediation_roadmap": []
                },
                confidence=0.0,
                execution_time_ms=(time.time() - start_time) * 1000,
                errors=[str(e)]
            )

    async def reflect(self, result: AgentResult) -> Reflection:
        """
        Verify synthesis quality. Synthesis doesn't need retry logic.
        """
        return Reflection(
            agent_name=self.name,
            confidence=result.confidence,
            needs_retry=False,
            reasoning="Synthesis complete"
        )

    async def synthesize(
        self,
        violations: List[Dict[str, Any]],
        frameworks: List[str],
        scratchpad: Optional[SharedMemory] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for synthesis.

        Args:
            violations: List of detected violations.
            frameworks: Frameworks that were analyzed.
            scratchpad: SharedMemory with judge reasoning.

        Returns:
            Synthesis result with executive summary, prioritized findings, etc.
        """
        if scratchpad:
            self.scratchpad = scratchpad

        context = {
            "violations": violations,
            "frameworks": frameworks
        }

        result = await self.run("Generate compliance report", context)
        return result.data

    async def _generate_executive_summary(
        self,
        violations: List[Dict[str, Any]],
        frameworks: List[str],
        risk_score: int,
        iterations: int,
        judge_reasoning: Dict[str, Any]
    ) -> str:
        """
        Use Claude to generate a narrative executive summary.
        """
        if not violations:
            return (
                f"The AI system was evaluated against {', '.join(f.upper() for f in frameworks)} "
                f"regulatory frameworks. No compliance violations were detected. "
                f"The system appears to meet the evaluated regulatory requirements. "
                f"However, compliance is an ongoing process, and regular re-evaluation "
                f"is recommended as regulations evolve and system capabilities change."
            )

        # Prepare data for prompt
        severity_breakdown = self._format_severity_breakdown(violations)
        key_findings = self._format_key_findings(violations[:5])
        reasoning_summary = self._format_reasoning_summary(judge_reasoning)

        prompt = self.SYNTHESIS_PROMPT.format(
            frameworks=", ".join(f.upper() for f in frameworks),
            violation_count=len(violations),
            risk_score=risk_score,
            iterations=iterations,
            severity_breakdown=severity_breakdown,
            key_findings=key_findings,
            reasoning_summary=reasoning_summary
        )

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Record LLM usage
            if self.scratchpad:
                self.scratchpad.record_llm_call(
                    response.usage.input_tokens,
                    response.usage.output_tokens
                )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            return self._generate_fallback_summary(violations, frameworks, risk_score)

    def _generate_fallback_summary(
        self,
        violations: List[Dict[str, Any]],
        frameworks: List[str],
        risk_score: int
    ) -> str:
        """Generate a basic summary if LLM call fails."""
        critical = len([v for v in violations if v.get("severity") == "CRITICAL"])
        major = len([v for v in violations if v.get("severity") == "MAJOR"])

        status = "critical attention" if critical > 0 else "review" if major > 0 else "minor adjustments"

        return (
            f"The compliance assessment identified {len(violations)} violation(s) across "
            f"{', '.join(f.upper() for f in frameworks)} frameworks, resulting in a risk score of {risk_score}/100. "
            f"The system requires {status} before deployment. "
            f"Please review the detailed findings below for specific remediation guidance."
        )

    def _prioritize_by_impact(self, violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort violations by business impact.

        Priority order:
        1. Severity (CRITICAL > MAJOR > MINOR)
        2. Confidence (higher confidence = higher priority)
        3. Framework (GDPR fines are highest)
        """
        framework_weight = {"GDPR": 3, "EUAI": 2, "SOX": 1}
        severity_weight = {"CRITICAL": 100, "MAJOR": 50, "MINOR": 10}

        def impact_score(v):
            sev = severity_weight.get(v.get("severity", "MINOR"), 0)
            fw = framework_weight.get(v.get("framework", "").upper(), 1)
            conf = v.get("confidence", 0.5)
            return sev * fw * conf

        sorted_violations = sorted(violations, key=impact_score, reverse=True)

        # Add priority rank
        for i, v in enumerate(sorted_violations):
            v["priority_rank"] = i + 1

        return sorted_violations

    def _generate_remediation_roadmap(
        self,
        violations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable remediation steps with effort estimates.
        """
        roadmap = []

        for i, violation in enumerate(violations[:10]):  # Top 10 priorities
            effort = self._estimate_effort(violation)
            timeline = violation.get("timeline", "Short-term")

            roadmap.append({
                "priority": i + 1,
                "title": violation.get("article_violated", "Unknown Violation"),
                "framework": violation.get("framework", "Unknown"),
                "severity": violation.get("severity", "MINOR"),
                "issue": violation.get("issue", ""),
                "remediation_steps": violation.get("remediation_steps", []),
                "engineering_scope": violation.get("engineering_scope", ""),
                "estimated_effort": effort,
                "timeline": timeline,
                "dependencies": violation.get("dependencies", [])
            })

        return roadmap

    def _calculate_confidence_improvements(self) -> Dict[str, Any]:
        """
        Analyze how the reflection loop improved confidence.
        """
        if not self.scratchpad:
            return {"improved": False, "iterations": 1}

        history = self.scratchpad.get_iteration_history()

        if len(history) < 2:
            return {"improved": False, "iterations": 1}

        # Find iteration end records
        iteration_ends = [
            h for h in history
            if isinstance(h, dict) and h.get("action") == "iteration_end"
        ]

        if len(iteration_ends) < 2:
            return {"improved": False, "iterations": len(iteration_ends) or 1}

        first_conf = iteration_ends[0].get("changes", {}).get("avg_confidence", 0)
        last_conf = iteration_ends[-1].get("changes", {}).get("avg_confidence", 0)

        return {
            "improved": last_conf > first_conf,
            "iterations": len(iteration_ends),
            "initial_avg_confidence": round(first_conf, 3),
            "final_avg_confidence": round(last_conf, 3),
            "improvement": round(last_conf - first_conf, 3)
        }

    def _calculate_risk_score(self, violations: List[Dict[str, Any]]) -> int:
        """Calculate risk score from violations (0-100)."""
        if not violations:
            return 0

        severity_weights = {
            "CRITICAL": 40,
            "MAJOR": 25,
            "MINOR": 10,
            "NONE": 0
        }

        total_score = 0
        for violation in violations:
            severity = violation.get("severity", "NONE")
            confidence = violation.get("confidence", 0.5)
            weight = severity_weights.get(severity, 0)
            total_score += weight * confidence

        return min(int(total_score), 100)

    def _count_severities(self, violations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count violations by severity."""
        counts = {"CRITICAL": 0, "MAJOR": 0, "MINOR": 0}
        for v in violations:
            sev = v.get("severity", "MINOR")
            if sev in counts:
                counts[sev] += 1
        return counts

    def _estimate_effort(self, violation: Dict[str, Any]) -> str:
        """Estimate remediation effort based on complexity and severity."""
        complexity = violation.get("complexity", "Medium")
        severity = violation.get("severity", "MINOR")

        effort_matrix = {
            ("High", "CRITICAL"): "4-8 weeks",
            ("High", "MAJOR"): "2-4 weeks",
            ("High", "MINOR"): "1-2 weeks",
            ("Medium", "CRITICAL"): "2-4 weeks",
            ("Medium", "MAJOR"): "1-2 weeks",
            ("Medium", "MINOR"): "3-5 days",
            ("Low", "CRITICAL"): "1-2 weeks",
            ("Low", "MAJOR"): "3-5 days",
            ("Low", "MINOR"): "1-2 days",
        }

        return effort_matrix.get((complexity, severity), "1-2 weeks")

    def _format_severity_breakdown(self, violations: List[Dict[str, Any]]) -> str:
        """Format severity counts for prompt."""
        counts = self._count_severities(violations)
        return f"CRITICAL: {counts['CRITICAL']}, MAJOR: {counts['MAJOR']}, MINOR: {counts['MINOR']}"

    def _format_key_findings(self, violations: List[Dict[str, Any]]) -> str:
        """Format top violations for prompt."""
        if not violations:
            return "No violations detected."

        lines = []
        for v in violations:
            line = f"- [{v.get('severity', 'N/A')}] {v.get('framework', 'Unknown')} {v.get('article_violated', '')}: {v.get('issue', 'N/A')}"
            lines.append(line)

        return "\n".join(lines)

    def _format_reasoning_summary(self, judge_reasoning: Dict[str, Any]) -> str:
        """Format judge reasoning for prompt."""
        if not judge_reasoning:
            return "No detailed reasoning available."

        lines = []
        for judge_id, data in judge_reasoning.items():
            conf = data.get("confidence", "N/A")
            violation = "Violation detected" if data.get("violation_detected") else "No violation"
            lines.append(f"- {judge_id}: {violation} (confidence: {conf})")

        return "\n".join(lines) if lines else "No detailed reasoning available."
