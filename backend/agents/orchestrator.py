"""
Orchestrator Agent for Sovereign V5 Multi-Agent System

The Orchestrator receives a GOAL (not instructions), plans execution,
coordinates all agents, and manages the reflection/retry loop.

This is the main entry point for the agentic compliance analysis flow.
"""

import os
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import time

from anthropic import Anthropic

from .base_agent import Agent, AgentPlan, AgentResult, Reflection, CONFIDENCE_THRESHOLD
from .shared_memory import SharedMemory

logger = logging.getLogger(__name__)


class OrchestratorAgent(Agent):
    """
    Orchestrator Agent that coordinates the multi-agent compliance analysis.

    Responsibilities:
        - Analyze input to determine which frameworks apply
        - Create execution plan dynamically
        - Invoke Researcher for context gathering
        - Run Validator Agents (judges) in parallel
        - Monitor for low-confidence flags
        - Trigger reflection/retry cycle when needed
        - Invoke Synthesizer for final report generation

    Tools:
        - invoke_researcher: Fetch regulatory context
        - invoke_validators: Run compliance judges
        - invoke_synthesizer: Generate final report
        - request_human_review: Escalate uncertain findings
    """

    TOOLS = [
        "invoke_researcher",
        "invoke_validators",
        "invoke_synthesizer",
        "request_human_review"
    ]

    PLANNING_PROMPT = """You are an expert compliance orchestrator for AI system evaluation.

Given the following goal and context, create an execution plan.

## Goal
{goal}

## Context
System Description: {description}
Requested Frameworks: {frameworks}
Risk Tolerance: {risk_tolerance}

## Available Tools
1. invoke_researcher - Fetch relevant regulatory context from RAG
2. invoke_validators - Run compliance judges (GDPR, SOX, EU AI Act)
3. invoke_synthesizer - Generate executive summary and remediation roadmap
4. request_human_review - Escalate findings with low confidence

## Instructions
Analyze the goal and determine:
1. Which frameworks are most relevant to this system
2. What specific regulatory areas to focus on
3. Whether cross-framework analysis is needed
4. Risk areas to prioritize

Respond with a JSON execution plan:
{{
    "frameworks_to_analyze": ["gdpr", "sox", "euai"],
    "priority_areas": ["automated decision-making", "data retention", "audit trails"],
    "cross_framework_concerns": ["data governance", "AI transparency"],
    "execution_sequence": [
        {{"step": 1, "action": "invoke_researcher", "params": {{"focus": "..."}}}},
        {{"step": 2, "action": "invoke_validators", "params": {{"parallel": true}}}},
        {{"step": 3, "action": "invoke_synthesizer", "params": {{}}}}
    ],
    "risk_assessment": "high|medium|low",
    "estimated_complexity": "high|medium|low"
}}"""

    REFLECTION_PROMPT = """You are analyzing the results of a compliance evaluation.

## Original Goal
{goal}

## Execution Results
Violations Found: {violation_count}
Average Confidence: {avg_confidence:.2f}
Low Confidence Flags: {low_confidence_count}

## Low Confidence Details
{low_confidence_details}

## Judge Results Summary
{judge_summary}

## Instructions
Assess the quality of this evaluation:
1. Is the confidence level sufficient (threshold: {confidence_threshold})?
2. Are there critical gaps that need additional context?
3. Should any judges be re-run with more information?

Respond with a JSON reflection:
{{
    "overall_confidence": 0.0-1.0,
    "needs_retry": true|false,
    "reasoning": "explanation of assessment",
    "gaps_identified": ["gap1", "gap2"],
    "context_needed": ["specific context to fetch"],
    "judges_to_retry": ["judge_id1", "judge_id2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}"""

    def __init__(
        self,
        scratchpad: Optional[SharedMemory] = None,
        api_key: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        max_iterations: int = 3
    ):
        """
        Initialize the Orchestrator Agent.

        Args:
            scratchpad: SharedMemory for inter-agent communication.
            api_key: Anthropic API key.
            confidence_threshold: Minimum confidence for acceptance.
            max_iterations: Max plan/act/reflect cycles.
        """
        super().__init__(
            name="orchestrator",
            tools=self.TOOLS,
            scratchpad=scratchpad or SharedMemory(),
            confidence_threshold=confidence_threshold,
            max_iterations=max_iterations
        )

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        # Create Anthropic client
        import httpx
        http_client = httpx.Client(proxy=None)
        self._client = Anthropic(api_key=self.api_key, http_client=http_client)
        self.model = "claude-haiku-4-5"

        # Lazy-loaded components
        self._rag_engine = None
        self._judges = None

        logger.info("OrchestratorAgent initialized")

    def _get_rag_engine(self):
        """Lazy load RAG engine."""
        if self._rag_engine is None:
            from backend.rag.rag_engine import RAGEngine
            self._rag_engine = RAGEngine()
        return self._rag_engine

    def _get_judges(self) -> Dict[str, List]:
        """Lazy load all 9 compliance judges."""
        if self._judges is None:
            from backend.judges import (
                GDPRArticle22Judge,
                GDPRArticle17Judge,
                GDPRArticle32Judge,
                SOXSection404Judge,
                SOXSection302Judge,
                SOXAuditTrailJudge,
                EUAIHighRiskJudge,
                EUAIProhibitedPracticesJudge,
                EUAITransparencyJudge,
            )
            self._judges = {
                "gdpr": [
                    GDPRArticle22Judge(),
                    GDPRArticle17Judge(),
                    GDPRArticle32Judge(),
                ],
                "sox": [
                    SOXSection404Judge(),
                    SOXSection302Judge(),
                    SOXAuditTrailJudge(),
                ],
                "euai": [
                    EUAIHighRiskJudge(),
                    EUAIProhibitedPracticesJudge(),
                    EUAITransparencyJudge(),
                ],
            }
        return self._judges

    async def plan(self, goal: str, context: Dict[str, Any]) -> AgentPlan:
        """
        Create execution plan based on goal and context.

        Uses Claude to analyze the submission and determine optimal
        framework selection and execution sequence.
        """
        description = context.get("description", "")
        frameworks = context.get("frameworks", ["gdpr", "sox", "euai"])
        risk_tolerance = context.get("risk_tolerance", "medium")

        # Check if we're in a retry iteration
        previous_reflection = context.get("previous_reflection")
        if previous_reflection:
            # Adjust plan based on previous reflection
            gaps = previous_reflection.get("gaps_identified", [])
            context_needed = previous_reflection.get("context_needed", [])
            logger.info(f"Planning retry iteration with {len(gaps)} gaps to address")

        try:
            # OPTIMIZATION: Skip Claude planning call - execution steps are deterministic
            # The planning phase was taking 200+ seconds due to Claude API latency
            # We already know: frameworks from context, steps are always researcher→validators→synthesizer
            logger.info(f"Creating plan for {len(frameworks)} frameworks (skipping Claude call)")

            plan_data = {
                "frameworks_to_analyze": frameworks,
                "priority_areas": [],
                "execution_sequence": [
                    {"step": 1, "action": "invoke_researcher"},
                    {"step": 2, "action": "invoke_validators"},
                    {"step": 3, "action": "invoke_synthesizer"}
                ],
                "estimated_complexity": "medium" if len(frameworks) <= 2 else "high"
            }

            # CRITICAL: Add original context to plan metadata so act() can access it
            # Without this, act() receives empty description and RAG returns 0 chunks
            plan_data["description"] = description
            plan_data["original_frameworks"] = frameworks

            # Store plan in scratchpad
            if self.scratchpad:
                self.scratchpad.set_plan(plan_data)

            return AgentPlan(
                agent_name=self.name,
                goal=goal,
                steps=[s.get("action", "") for s in plan_data.get("execution_sequence", [])],
                tools_to_use=self.TOOLS,
                estimated_complexity=plan_data.get("estimated_complexity", "medium"),
                context_needed=plan_data.get("priority_areas", []),
                metadata=plan_data
            )

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Return default plan on failure - CRITICAL: must include description and frameworks
            return AgentPlan(
                agent_name=self.name,
                goal=goal,
                steps=["invoke_researcher", "invoke_validators", "invoke_synthesizer"],
                tools_to_use=self.TOOLS,
                estimated_complexity="medium",
                metadata={
                    "error": str(e),
                    "description": description,
                    "original_frameworks": frameworks,
                    "frameworks_to_analyze": frameworks
                }
            )

    async def act(self, plan: AgentPlan) -> AgentResult:
        """
        Execute the plan by invoking sub-agents.

        Flow:
        1. Invoke Researcher to get regulatory context
        2. Run Validators (judges) in parallel
        3. Collect results and check for low confidence
        """
        start_time = time.time()
        context = plan.metadata
        description = context.get("description", "")
        # Use original_frameworks as fallback in case Claude's response doesn't include them
        frameworks = context.get("frameworks_to_analyze") or context.get("original_frameworks", ["gdpr", "sox", "euai"])

        # DEFENSIVE: Fail fast if description is empty (prevents 4-minute timeout)
        if not description or not description.strip():
            logger.error("CRITICAL: Empty description in act() - check plan.metadata flow")
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={"violations": [], "frameworks_analyzed": frameworks, "chunks_retrieved": 0},
                confidence=0.0,
                execution_time_ms=(time.time() - start_time) * 1000,
                errors=["Empty submission provided. Unable to analyze."],
                warnings=["This may indicate a bug in the plan/act data flow."]
            )

        violations = []
        errors = []
        warnings = []

        try:
            # Step 1: Retrieve regulatory context
            # PERF: use_routing=False skips Claude classification call (saves ~3-5s)
            logger.info(f"[ACT] Step 1: Starting RAG retrieval for {len(description)} char description")
            rag = self._get_rag_engine()
            logger.info("[ACT] RAG engine obtained, calling retrieve()...")
            retrieved_chunks = rag.retrieve(
                query=description,
                frameworks=frameworks,
                top_k=15,
                use_routing=False
            )
            logger.info(f"[ACT] RAG retrieval completed: {len(retrieved_chunks)} chunks")

            if self.scratchpad:
                self.scratchpad.append_finding("researcher", {
                    "query": description[:500],
                    "chunks_retrieved": len(retrieved_chunks),
                    "frameworks": frameworks
                })

            logger.info(f"Retrieved {len(retrieved_chunks)} chunks")

            # Step 2: Run judges in parallel
            logger.info("[ACT] Step 2: Getting judges...")
            judges = self._get_judges()
            logger.info(f"[ACT] Got {sum(len(j) for j in judges.values())} judges")

            # Prepare judge tasks
            judge_tasks = []
            for framework in frameworks:
                framework_lower = framework.lower()
                framework_judges = judges.get(framework_lower, [])
                framework_chunks = [
                    c for c in retrieved_chunks
                    if c.get("framework", "").lower() == framework_lower
                ]

                for judge in framework_judges:
                    judge_tasks.append((judge, description, framework_chunks))

            # Execute judges using asyncio.to_thread for sync judges
            async def run_judge_async(judge, submission, chunks):
                """Wrap sync judge.evaluate in async."""
                try:
                    result = await asyncio.to_thread(
                        judge.evaluate,
                        submission=submission,
                        retrieved_chunks=chunks
                    )
                    return (judge.judge_id, result, None)
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Judge {judge.judge_id} failed: {error_msg}")
                    return (judge.judge_id, None, error_msg)

            # Run all judges concurrently
            logger.info(f"[ACT] Running {len(judge_tasks)} judge tasks in parallel...")
            tasks = [
                run_judge_async(judge, submission, chunks)
                for judge, submission, chunks in judge_tasks
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"[ACT] All {len(tasks)} judge tasks completed")

            # Process results
            failed_judges = []
            successful_judges = 0

            for item in results:
                if isinstance(item, Exception):
                    errors.append(str(item))
                    failed_judges.append({"judge_id": "unknown", "error": str(item)})
                    continue

                judge_id, result, error_msg = item

                # Track failed judges
                if error_msg:
                    failed_judges.append({"judge_id": judge_id, "error": error_msg})
                    errors.append(f"{judge_id}: {error_msg}")
                    continue

                successful_judges += 1

                if result:
                    # Store reasoning in scratchpad
                    if self.scratchpad:
                        self.scratchpad.set_judge_reasoning(judge_id, result)

                    # Check for violations
                    if result.get("violation_detected"):
                        violations.append(result)

                        # Flag low confidence
                        confidence = result.get("confidence", 0)
                        if confidence < self.confidence_threshold:
                            if self.scratchpad:
                                self.scratchpad.flag_low_confidence(
                                    judge_id=judge_id,
                                    confidence=confidence,
                                    reason=f"Confidence {confidence:.2f} below threshold {self.confidence_threshold}",
                                    context_needed=[f"Additional context for {result.get('article_violated', 'unknown')}"]
                                )

            # If ALL judges failed, mark as failure
            all_judges_failed = failed_judges and successful_judges == 0

            # Calculate overall confidence
            if violations:
                avg_confidence = sum(v.get("confidence", 0) for v in violations) / len(violations)
            elif all_judges_failed:
                avg_confidence = 0.0  # All judges failed = no confidence
            else:
                avg_confidence = 1.0  # No violations and judges succeeded = high confidence in clean result

            execution_time = (time.time() - start_time) * 1000

            logger.info(
                f"Execution complete: {len(violations)} violations, "
                f"{successful_judges} judges succeeded, {len(failed_judges)} failed, "
                f"avg confidence: {avg_confidence:.2f}, "
                f"time: {execution_time:.0f}ms"
            )

            # Log warning if some judges failed
            if failed_judges:
                logger.warning(f"Failed judges: {[j['judge_id'] for j in failed_judges]}")

            return AgentResult(
                agent_name=self.name,
                success=not all_judges_failed,  # Fail if ALL judges failed
                data={
                    "violations": violations,
                    "chunks_retrieved": len(retrieved_chunks),
                    "judges_run": len(judge_tasks),
                    "judges_succeeded": successful_judges,
                    "judges_failed": len(failed_judges),
                    "failed_judges": failed_judges if failed_judges else None,
                    "frameworks_analyzed": frameworks
                },
                confidence=avg_confidence,
                execution_time_ms=execution_time,
                tools_used=["invoke_researcher", "invoke_validators"],
                errors=errors,
                warnings=warnings
            )

        except Exception as e:
            logger.error(f"Orchestrator action failed: {e}")
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={"violations": violations},
                confidence=0.0,
                execution_time_ms=(time.time() - start_time) * 1000,
                errors=[str(e)]
            )

    async def reflect(self, result: AgentResult) -> Reflection:
        """
        Reflect on execution results and determine if retry is needed.

        Checks:
        - Overall confidence level
        - Low confidence flags
        - Coverage of requested frameworks
        """
        violations = result.data.get("violations", [])
        low_confidence_flags = []
        if self.scratchpad:
            low_confidence_flags = self.scratchpad.get_low_confidence_flags()

        # Calculate metrics
        violation_count = len(violations)
        avg_confidence = result.confidence
        low_confidence_count = len(low_confidence_flags)

        # Prepare reflection prompt
        judge_summary = "\n".join([
            f"- {v.get('judge_id', 'unknown')}: {v.get('severity', 'N/A')} "
            f"(confidence: {v.get('confidence', 0):.2f})"
            for v in violations
        ]) or "No violations detected"

        low_confidence_details = "\n".join([
            f"- {f.get('judge_id', 'unknown')}: {f.get('reason', 'N/A')}"
            for f in low_confidence_flags
        ]) or "None"

        try:
            prompt = self.REFLECTION_PROMPT.format(
                goal=result.metadata.get("goal", "Compliance analysis"),
                violation_count=violation_count,
                avg_confidence=avg_confidence,
                low_confidence_count=low_confidence_count,
                low_confidence_details=low_confidence_details,
                judge_summary=judge_summary,
                confidence_threshold=self.confidence_threshold
            )

            response = self._client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            if self.scratchpad:
                self.scratchpad.record_llm_call(
                    response.usage.input_tokens,
                    response.usage.output_tokens
                )

            # Parse response
            response_text = response.content[0].text

            import json
            import re

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                reflection_data = json.loads(json_match.group())
            else:
                # Fallback
                reflection_data = {
                    "overall_confidence": avg_confidence,
                    "needs_retry": low_confidence_count > 0 and self._iteration_count < self.max_iterations,
                    "reasoning": "Unable to parse LLM response",
                    "gaps_identified": [],
                    "context_needed": []
                }

            return Reflection(
                agent_name=self.name,
                confidence=reflection_data.get("overall_confidence", avg_confidence),
                needs_retry=reflection_data.get("needs_retry", False),
                reasoning=reflection_data.get("reasoning", ""),
                gaps_identified=reflection_data.get("gaps_identified", []),
                context_needed=reflection_data.get("context_needed", []),
                suggestions=reflection_data.get("suggestions", []),
                iteration=self._iteration_count
            )

        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            # Conservative reflection on failure
            return Reflection(
                agent_name=self.name,
                confidence=avg_confidence,
                needs_retry=False,  # Don't retry on reflection failure
                reasoning=f"Reflection error: {str(e)}",
                gaps_identified=[],
                context_needed=[],
                iteration=self._iteration_count
            )

    async def analyze(
        self,
        description: str,
        frameworks: List[str],
        risk_tolerance: str = "medium",
        include_synthesis: bool = True
    ) -> Dict[str, Any]:
        """
        Main entry point for agentic compliance analysis.

        This is the high-level API that external code should call.

        Args:
            description: AI system description to analyze.
            frameworks: List of frameworks to check against.
            risk_tolerance: "low", "medium", or "high".
            include_synthesis: Whether to generate executive summary.

        Returns:
            Analysis results including violations, risk score, synthesis, and agent trace.
        """
        # Reset scratchpad for new analysis
        logger.info("[ANALYZE] Starting analysis...")
        if self.scratchpad:
            self.scratchpad.clear()

        goal = f"Analyze the AI system for compliance with {', '.join(frameworks)} regulations"

        context = {
            "description": description,
            "frameworks": frameworks,
            "risk_tolerance": risk_tolerance
        }

        # Run the agent loop (plan/act/reflect with iterations)
        logger.info("[ANALYZE] Calling self.run()...")
        result = await self.run(goal, context)
        logger.info("[ANALYZE] self.run() completed")

        # Calculate risk score
        violations = result.data.get("violations", [])
        risk_score = self._calculate_risk_score(violations)

        # Build base response
        response = {
            "status": "success" if result.success else "error",
            "violations": violations,
            "risk_score": risk_score,
            "frameworks_analyzed": result.data.get("frameworks_analyzed", frameworks),
            "chunks_retrieved": result.data.get("chunks_retrieved", 0),
            "iterations": self._iteration_count,
            "confidence": result.confidence,
            "errors": result.errors,
            "warnings": result.warnings
        }

        # Generate synthesis if requested
        if include_synthesis:
            try:
                logger.info("[ANALYZE] Starting synthesis...")
                from .synthesizer import SynthesisAgent

                synthesizer = SynthesisAgent(scratchpad=self.scratchpad)
                synthesis = await synthesizer.synthesize(
                    violations=violations,
                    frameworks=frameworks,
                    scratchpad=self.scratchpad
                )
                logger.info("[ANALYZE] Synthesis completed")

                logger.info("[ANALYZE] Setting response fields from synthesis...")
                response["executive_summary"] = synthesis.get("executive_summary", "")
                response["prioritized_findings"] = synthesis.get("prioritized_findings", [])
                response["remediation_roadmap"] = synthesis.get("remediation_roadmap", [])
                response["confidence_improvements"] = synthesis.get("confidence_improvements", {})
                logger.info("[ANALYZE] Response fields set")

            except Exception as e:
                logger.error(f"Synthesis failed: {e}")
                response["executive_summary"] = "Unable to generate executive summary."
                response["synthesis_error"] = str(e)

        # Skip agent trace - lightweight version still causes memory issues
        # TODO: Debug to_lightweight_dict() method
        response["agent_trace"] = {"note": "Agent trace disabled to reduce memory usage"}

        logger.info("[ANALYZE] Returning response from analyze()")
        return response

    async def analyze_with_retry(
        self,
        description: str,
        frameworks: List[str],
        risk_tolerance: str = "medium"
    ) -> Dict[str, Any]:
        """
        Enhanced analysis with explicit reflection and retry loop.

        This method provides more control over the iteration process
        and fetches additional context for low-confidence findings.
        """
        if self.scratchpad:
            self.scratchpad.clear()

        violations = []
        all_chunks = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Starting iteration {iteration}/{self.max_iterations}")

            if self.scratchpad:
                self.scratchpad.log_iteration_start(iteration)

            # Step 1: Retrieve context (initial or targeted)
            rag = self._get_rag_engine()

            if iteration == 1:
                # Initial broad retrieval
                # PERF: use_routing=False skips Claude classification call
                chunks = rag.retrieve(
                    query=description,
                    frameworks=frameworks,
                    top_k=15,
                    use_routing=False
                )
                all_chunks = chunks
            else:
                # Targeted retrieval for low-confidence judges
                low_conf_judges = self.scratchpad.get_judges_needing_retry() if self.scratchpad else []
                for judge_id in low_conf_judges:
                    flag = self.scratchpad.get_low_confidence_flag(judge_id)
                    if flag and flag.get("context_needed"):
                        additional = rag.retrieve(
                            query=" ".join(flag["context_needed"]),
                            frameworks=frameworks,
                            top_k=5,
                            use_routing=False
                        )
                        self.scratchpad.add_additional_context(judge_id, additional)
                        all_chunks.extend(additional)

            # Step 2: Run judges
            judges = self._get_judges()
            judge_tasks = []

            for framework in frameworks:
                framework_lower = framework.lower()
                framework_judges = judges.get(framework_lower, [])
                framework_chunks = [c for c in all_chunks if c.get("framework", "").lower() == framework_lower]

                for judge in framework_judges:
                    # Add any additional context for this judge
                    additional = self.scratchpad.get_additional_context(judge.judge_id) if self.scratchpad else []
                    combined_chunks = framework_chunks + additional

                    judge_tasks.append(self._run_judge_async(judge, description, combined_chunks))

            results = await asyncio.gather(*judge_tasks, return_exceptions=True)

            # Process results
            iteration_violations = []
            low_confidence_count = 0

            for item in results:
                if isinstance(item, Exception):
                    continue

                judge_id, result = item
                if result:
                    if self.scratchpad:
                        self.scratchpad.set_judge_reasoning(judge_id, result)

                    if result.get("violation_detected"):
                        iteration_violations.append(result)

                        confidence = result.get("confidence", 0)
                        if confidence < self.confidence_threshold:
                            low_confidence_count += 1
                            if self.scratchpad:
                                self.scratchpad.flag_low_confidence(
                                    judge_id=judge_id,
                                    confidence=confidence,
                                    reason=f"Confidence {confidence:.2f} below threshold",
                                    context_needed=[f"More context for {result.get('article_violated', '')}"]
                                )

            violations = iteration_violations

            # Calculate avg confidence
            avg_conf = sum(v.get("confidence", 0) for v in violations) / len(violations) if violations else 1.0

            if self.scratchpad:
                self.scratchpad.log_iteration_end(iteration, avg_conf, len(violations))

            # Check if we can stop
            if low_confidence_count == 0 or iteration == self.max_iterations:
                logger.info(f"Stopping at iteration {iteration}: low_conf={low_confidence_count}")
                break

            # Clear flags for next iteration
            if self.scratchpad:
                for judge_id in self.scratchpad.get_judges_needing_retry():
                    self.scratchpad.clear_flags_for_judge(judge_id)

        # Generate synthesis
        from .synthesizer import SynthesisAgent
        synthesizer = SynthesisAgent(scratchpad=self.scratchpad)
        synthesis = await synthesizer.synthesize(violations, frameworks, self.scratchpad)

        return {
            "status": "success",
            "violations": violations,
            "risk_score": self._calculate_risk_score(violations),
            "frameworks_analyzed": frameworks,
            "chunks_retrieved": len(all_chunks),
            "iterations": iteration,
            "confidence": avg_conf,
            "executive_summary": synthesis.get("executive_summary", ""),
            "prioritized_findings": synthesis.get("prioritized_findings", []),
            "remediation_roadmap": synthesis.get("remediation_roadmap", []),
            "confidence_improvements": synthesis.get("confidence_improvements", {}),
            "agent_trace": {"note": "Agent trace disabled to reduce memory usage"}
        }

    async def _run_judge_async(self, judge, submission: str, chunks: List[Dict]) -> Tuple[str, Optional[Dict]]:
        """Wrap sync judge.evaluate in async."""
        try:
            result = await asyncio.to_thread(
                judge.evaluate,
                submission=submission,
                retrieved_chunks=chunks
            )
            return (judge.judge_id, result)
        except Exception as e:
            logger.error(f"Judge {judge.judge_id} failed: {e}")
            return (judge.judge_id, None)

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
