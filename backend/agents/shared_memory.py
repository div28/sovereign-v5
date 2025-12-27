"""
Shared Memory (Scratchpad) for Sovereign V5 Multi-Agent System

Provides persistent context that all agents can read and write to.
Enables inter-agent communication and reasoning transparency.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from threading import Lock
import json

logger = logging.getLogger(__name__)


@dataclass
class LowConfidenceFlag:
    """Flag for low-confidence findings that need review."""

    judge_id: str
    confidence: float
    reason: str
    context_needed: List[str]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "judge_id": self.judge_id,
            "confidence": self.confidence,
            "reason": self.reason,
            "context_needed": self.context_needed,
            "created_at": self.created_at
        }


@dataclass
class IterationRecord:
    """Record of what changed in each iteration."""

    iteration: int
    agent: str
    action: str
    changes: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "agent": self.agent,
            "action": self.action,
            "changes": self.changes,
            "timestamp": self.timestamp
        }


class SharedMemory:
    """
    Shared memory (scratchpad) for inter-agent communication.

    All agents can read from and write to this shared context.
    Thread-safe for concurrent access during parallel execution.

    Sections:
        - orchestrator_plan: Current execution plan from orchestrator
        - researcher_findings: Retrieved documents and their relevance
        - judge_reasoning: Each judge's detailed reasoning chain
        - low_confidence_flags: Findings that need re-evaluation
        - iteration_history: What changed between iterations

    Usage:
        scratchpad = SharedMemory()
        scratchpad.set_plan({"frameworks": ["gdpr", "sox"], ...})
        scratchpad.append_finding("researcher", {"query": "...", "results": [...]})
        scratchpad.flag_low_confidence("gdpr_article_22", 0.55, "Ambiguous consent")
    """

    def __init__(self):
        """Initialize empty shared memory."""
        self._lock = Lock()
        self._created_at = datetime.utcnow().isoformat()

        # Core sections
        self._orchestrator_plan: Dict[str, Any] = {}
        self._researcher_findings: List[Dict[str, Any]] = []
        self._judge_reasoning: Dict[str, Dict[str, Any]] = {}
        self._low_confidence_flags: List[LowConfidenceFlag] = []
        self._iteration_history: List[IterationRecord] = []

        # Agent traces for debugging
        self._agent_plans: Dict[str, List[Dict[str, Any]]] = {}
        self._agent_results: Dict[str, List[Dict[str, Any]]] = {}
        self._agent_reflections: Dict[str, List[Dict[str, Any]]] = {}

        # Metadata
        self._current_iteration: int = 0
        self._total_llm_calls: int = 0
        self._total_tokens: Dict[str, int] = {"input": 0, "output": 0}

        logger.info("SharedMemory initialized")

    # =========================================================================
    # ORCHESTRATOR PLAN
    # =========================================================================

    def set_plan(self, plan: Dict[str, Any]) -> None:
        """
        Set the orchestrator's execution plan.

        Args:
            plan: Execution plan with frameworks, sequence, etc.
        """
        with self._lock:
            self._orchestrator_plan = plan
            self._record_iteration("orchestrator", "set_plan", {"plan": plan})
            logger.debug(f"Orchestrator plan set: {list(plan.keys())}")

    def get_plan(self) -> Dict[str, Any]:
        """Get the current orchestrator plan."""
        with self._lock:
            return self._orchestrator_plan.copy()

    def update_plan(self, updates: Dict[str, Any]) -> None:
        """Update specific fields in the orchestrator plan."""
        with self._lock:
            self._orchestrator_plan.update(updates)
            self._record_iteration("orchestrator", "update_plan", {"updates": updates})

    # =========================================================================
    # RESEARCHER FINDINGS
    # =========================================================================

    def append_finding(self, agent: str, finding: Dict[str, Any]) -> None:
        """
        Append a finding from the researcher agent.

        Args:
            agent: Agent name that produced the finding.
            finding: Finding data (query, results, relevance, etc.)
        """
        with self._lock:
            finding_with_meta = {
                "agent": agent,
                "timestamp": datetime.utcnow().isoformat(),
                **finding
            }
            self._researcher_findings.append(finding_with_meta)
            self._record_iteration(agent, "append_finding", {"query": finding.get("query", "")})
            logger.debug(f"Finding appended by {agent}")

    def get_findings(self, agent: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get researcher findings, optionally filtered by agent.

        Args:
            agent: Optional agent name to filter by.

        Returns:
            List of findings.
        """
        with self._lock:
            if agent:
                return [f for f in self._researcher_findings if f.get("agent") == agent]
            return self._researcher_findings.copy()

    def get_latest_findings(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most recent findings."""
        with self._lock:
            return self._researcher_findings[-limit:]

    # =========================================================================
    # JUDGE REASONING
    # =========================================================================

    def set_judge_reasoning(self, judge_id: str, reasoning: Dict[str, Any]) -> None:
        """
        Store a judge's reasoning chain.

        Args:
            judge_id: Unique identifier for the judge.
            reasoning: Reasoning data including verdict, evidence, confidence.
        """
        with self._lock:
            self._judge_reasoning[judge_id] = {
                "timestamp": datetime.utcnow().isoformat(),
                **reasoning
            }
            self._record_iteration(judge_id, "set_reasoning", {
                "confidence": reasoning.get("confidence", 0),
                "violation": reasoning.get("violation_detected", False)
            })
            logger.debug(f"Reasoning stored for {judge_id}")

    def get_judge_reasoning(self, judge_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get judge reasoning, optionally for a specific judge.

        Args:
            judge_id: Optional judge ID to get reasoning for.

        Returns:
            Reasoning dict or all judge reasonings.
        """
        with self._lock:
            if judge_id:
                return self._judge_reasoning.get(judge_id, {})
            return self._judge_reasoning.copy()

    def get_all_violations(self) -> List[Dict[str, Any]]:
        """Get all detected violations from judge reasoning."""
        with self._lock:
            violations = []
            for judge_id, reasoning in self._judge_reasoning.items():
                if reasoning.get("violation_detected", False):
                    violations.append({
                        "judge_id": judge_id,
                        **reasoning
                    })
            return violations

    # =========================================================================
    # LOW CONFIDENCE FLAGS
    # =========================================================================

    def flag_low_confidence(
        self,
        judge_id: str,
        confidence: float,
        reason: str,
        context_needed: Optional[List[str]] = None
    ) -> None:
        """
        Flag a low-confidence finding for potential retry.

        Args:
            judge_id: Judge that produced the low-confidence result.
            confidence: Confidence score (0-1).
            reason: Why confidence is low.
            context_needed: What additional context might help.
        """
        with self._lock:
            flag = LowConfidenceFlag(
                judge_id=judge_id,
                confidence=confidence,
                reason=reason,
                context_needed=context_needed or []
            )
            self._low_confidence_flags.append(flag)
            self._record_iteration(judge_id, "flag_low_confidence", {
                "confidence": confidence,
                "reason": reason
            })
            logger.info(f"Low confidence flag: {judge_id} ({confidence:.2f}) - {reason}")

    def get_low_confidence_flags(self) -> List[Dict[str, Any]]:
        """Get all low-confidence flags."""
        with self._lock:
            return [f.to_dict() for f in self._low_confidence_flags]

    def get_judges_needing_retry(self) -> List[str]:
        """Get list of judge IDs that need retry due to low confidence."""
        with self._lock:
            return list(set(f.judge_id for f in self._low_confidence_flags))

    def get_context_needed(self) -> List[str]:
        """Get aggregated list of additional context needed."""
        with self._lock:
            all_context = []
            for flag in self._low_confidence_flags:
                all_context.extend(flag.context_needed)
            return list(set(all_context))

    def clear_flags_for_judge(self, judge_id: str) -> None:
        """Clear low-confidence flags for a specific judge (after retry)."""
        with self._lock:
            self._low_confidence_flags = [
                f for f in self._low_confidence_flags
                if f.judge_id != judge_id
            ]
            logger.debug(f"Cleared flags for {judge_id}")

    # =========================================================================
    # ITERATION HISTORY
    # =========================================================================

    def _record_iteration(self, agent: str, action: str, changes: Dict[str, Any]) -> None:
        """Internal method to record iteration changes."""
        record = IterationRecord(
            iteration=self._current_iteration,
            agent=agent,
            action=action,
            changes=changes
        )
        self._iteration_history.append(record)

    def increment_iteration(self) -> int:
        """Increment and return the current iteration number."""
        with self._lock:
            self._current_iteration += 1
            logger.debug(f"Iteration incremented to {self._current_iteration}")
            return self._current_iteration

    def get_iteration_history(self) -> List[Dict[str, Any]]:
        """Get full iteration history."""
        with self._lock:
            return [r.to_dict() for r in self._iteration_history]

    def get_current_iteration(self) -> int:
        """Get current iteration number."""
        with self._lock:
            return self._current_iteration

    # =========================================================================
    # AGENT TRACES
    # =========================================================================

    def append_plan(self, agent: str, plan: Dict[str, Any]) -> None:
        """Append an agent's plan to traces."""
        with self._lock:
            if agent not in self._agent_plans:
                self._agent_plans[agent] = []
            self._agent_plans[agent].append(plan)

    def append_result(self, agent: str, result: Dict[str, Any]) -> None:
        """Append an agent's result to traces."""
        with self._lock:
            if agent not in self._agent_results:
                self._agent_results[agent] = []
            self._agent_results[agent].append(result)

    def append_reflection(self, agent: str, reflection: Dict[str, Any]) -> None:
        """Append an agent's reflection to traces."""
        with self._lock:
            if agent not in self._agent_reflections:
                self._agent_reflections[agent] = []
            self._agent_reflections[agent].append(reflection)

    # =========================================================================
    # METRICS
    # =========================================================================

    def record_llm_call(self, input_tokens: int, output_tokens: int) -> None:
        """Record LLM usage for cost tracking."""
        with self._lock:
            self._total_llm_calls += 1
            self._total_tokens["input"] += input_tokens
            self._total_tokens["output"] += output_tokens

    def get_metrics(self) -> Dict[str, Any]:
        """Get usage metrics."""
        with self._lock:
            return {
                "total_llm_calls": self._total_llm_calls,
                "total_tokens": self._total_tokens.copy(),
                "iterations": self._current_iteration,
                "low_confidence_count": len(self._low_confidence_flags),
                "judges_evaluated": len(self._judge_reasoning),
                "findings_count": len(self._researcher_findings)
            }

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize entire scratchpad to dictionary.

        Used for agent_trace response when include_agent_trace=true.
        """
        with self._lock:
            return {
                "created_at": self._created_at,
                "current_iteration": self._current_iteration,
                "orchestrator_plan": self._orchestrator_plan,
                "researcher_findings": self._researcher_findings,
                "judge_reasoning": self._judge_reasoning,
                "low_confidence_flags": [f.to_dict() for f in self._low_confidence_flags],
                "iteration_history": [r.to_dict() for r in self._iteration_history],
                "agent_traces": {
                    "plans": self._agent_plans,
                    "results": self._agent_results,
                    "reflections": self._agent_reflections
                },
                "metrics": self.get_metrics()
            }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def clear(self) -> None:
        """Clear all data (reset for new analysis)."""
        with self._lock:
            self._orchestrator_plan = {}
            self._researcher_findings = []
            self._judge_reasoning = {}
            self._low_confidence_flags = []
            self._iteration_history = []
            self._agent_plans = {}
            self._agent_results = {}
            self._agent_reflections = {}
            self._current_iteration = 0
            self._total_llm_calls = 0
            self._total_tokens = {"input": 0, "output": 0}
            self._additional_context: Dict[str, List[Dict]] = {}
            self._created_at = datetime.utcnow().isoformat()
            logger.info("SharedMemory cleared")

    # =========================================================================
    # ADDITIONAL CONTEXT (for reflection loop retries)
    # =========================================================================

    def add_additional_context(self, judge_id: str, context: List[Dict[str, Any]]) -> None:
        """
        Store additional context fetched for a specific judge during reflection.

        Args:
            judge_id: Judge that needs additional context.
            context: Additional regulatory chunks.
        """
        with self._lock:
            if not hasattr(self, '_additional_context'):
                self._additional_context = {}
            self._additional_context[judge_id] = context
            logger.debug(f"Added {len(context)} additional context chunks for {judge_id}")

    def get_additional_context(self, judge_id: str) -> List[Dict[str, Any]]:
        """Get additional context for a judge (fetched during reflection)."""
        with self._lock:
            if not hasattr(self, '_additional_context'):
                return []
            return self._additional_context.get(judge_id, [])

    def get_low_confidence_flag(self, judge_id: str) -> Optional[Dict[str, Any]]:
        """Get low-confidence flag for a specific judge."""
        with self._lock:
            for flag in self._low_confidence_flags:
                if flag.judge_id == judge_id:
                    return flag.to_dict()
            return None

    def log_iteration_start(self, iteration: int) -> None:
        """Log the start of a new iteration."""
        with self._lock:
            self._iteration_history.append(IterationRecord(
                iteration=iteration,
                agent="orchestrator",
                action="iteration_start",
                changes={"status": "started"}
            ))
            self._current_iteration = iteration
            logger.info(f"Iteration {iteration} started")

    def log_iteration_end(self, iteration: int, avg_confidence: float, violation_count: int) -> None:
        """Log the end of an iteration with summary metrics."""
        with self._lock:
            self._iteration_history.append(IterationRecord(
                iteration=iteration,
                agent="orchestrator",
                action="iteration_end",
                changes={
                    "status": "completed",
                    "avg_confidence": avg_confidence,
                    "violation_count": violation_count
                }
            ))
            logger.info(f"Iteration {iteration} completed: avg_confidence={avg_confidence:.2f}, violations={violation_count}")

    def __repr__(self) -> str:
        return (
            f"SharedMemory("
            f"iterations={self._current_iteration}, "
            f"findings={len(self._researcher_findings)}, "
            f"judges={len(self._judge_reasoning)}, "
            f"flags={len(self._low_confidence_flags)})"
        )
