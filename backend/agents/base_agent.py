"""
Base Agent Class for Sovereign V5 Multi-Agent System

Provides the foundational plan/act/reflect pattern for all agents.
Supports async execution with configurable confidence thresholds.
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Configurable confidence threshold (default 0.7)
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))


@dataclass
class AgentPlan:
    """Structured plan output from agent planning phase."""

    agent_name: str
    goal: str
    steps: List[str]
    tools_to_use: List[str]
    estimated_complexity: str  # "low", "medium", "high"
    context_needed: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "goal": self.goal,
            "steps": self.steps,
            "tools_to_use": self.tools_to_use,
            "estimated_complexity": self.estimated_complexity,
            "context_needed": self.context_needed,
            "metadata": self.metadata,
            "created_at": self.created_at
        }


@dataclass
class AgentResult:
    """Result output from agent action phase."""

    agent_name: str
    success: bool
    data: Dict[str, Any]
    confidence: float
    execution_time_ms: float = 0.0
    tools_used: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "success": self.success,
            "data": self.data,
            "confidence": self.confidence,
            "execution_time_ms": self.execution_time_ms,
            "tools_used": self.tools_used,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "created_at": self.created_at
        }


@dataclass
class Reflection:
    """Reflection output from agent reflection phase."""

    agent_name: str
    confidence: float
    needs_retry: bool
    reasoning: str
    gaps_identified: List[str] = field(default_factory=list)
    context_needed: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    iteration: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert reflection to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "confidence": self.confidence,
            "needs_retry": self.needs_retry,
            "reasoning": self.reasoning,
            "gaps_identified": self.gaps_identified,
            "context_needed": self.context_needed,
            "suggestions": self.suggestions,
            "iteration": self.iteration,
            "metadata": self.metadata,
            "created_at": self.created_at
        }


class Agent(ABC):
    """
    Abstract base class for all agents in the Sovereign multi-agent system.

    Implements the plan/act/reflect pattern with configurable iteration
    and confidence thresholds. Agents can use tools, communicate via
    SharedMemory, and request additional context when needed.

    Attributes:
        name: Unique identifier for this agent.
        tools: List of tool names this agent can use.
        scratchpad: Reference to SharedMemory for inter-agent communication.
        confidence_threshold: Minimum confidence to accept result without retry.
        max_iterations: Maximum number of plan/act/reflect cycles.
    """

    def __init__(
        self,
        name: str,
        tools: List[str],
        scratchpad: Optional[Any] = None,  # SharedMemory, optional to avoid circular import
        confidence_threshold: Optional[float] = None,
        max_iterations: int = 3
    ):
        """
        Initialize the agent.

        Args:
            name: Unique identifier for this agent.
            tools: List of tool names this agent can use.
            scratchpad: SharedMemory instance for inter-agent communication.
            confidence_threshold: Override default threshold (env: CONFIDENCE_THRESHOLD).
            max_iterations: Maximum plan/act/reflect cycles before giving up.
        """
        self.name = name
        self.tools = tools
        self.scratchpad = scratchpad
        self.confidence_threshold = confidence_threshold or CONFIDENCE_THRESHOLD
        self.max_iterations = max_iterations
        self._iteration_count = 0

        logger.info(
            f"Initialized {self.__class__.__name__} '{name}' with "
            f"{len(tools)} tools, threshold={self.confidence_threshold}"
        )

    @abstractmethod
    async def plan(self, goal: str, context: Dict[str, Any]) -> AgentPlan:
        """
        Planning phase: Decide what to do based on goal and context.

        Args:
            goal: The objective to achieve.
            context: Current context including previous results, scratchpad data.

        Returns:
            AgentPlan with steps and tools to use.
        """
        pass

    @abstractmethod
    async def act(self, plan: AgentPlan) -> AgentResult:
        """
        Action phase: Execute the plan.

        Args:
            plan: The plan to execute.

        Returns:
            AgentResult with data and confidence score.
        """
        pass

    @abstractmethod
    async def reflect(self, result: AgentResult) -> Reflection:
        """
        Reflection phase: Assess outcome and determine if retry needed.

        Args:
            result: The result from the action phase.

        Returns:
            Reflection with confidence assessment and retry decision.
        """
        pass

    def _update_context(
        self,
        context: Dict[str, Any],
        reflection: Reflection
    ) -> Dict[str, Any]:
        """
        Update context based on reflection for retry.

        Args:
            context: Current context.
            reflection: Reflection from previous iteration.

        Returns:
            Updated context with gaps and suggestions incorporated.
        """
        updated = context.copy()
        updated["previous_reflection"] = reflection.to_dict()
        updated["gaps_to_address"] = reflection.gaps_identified
        updated["context_needed"] = reflection.context_needed
        updated["iteration"] = self._iteration_count
        return updated

    async def run(
        self,
        goal: str,
        context: Dict[str, Any],
        max_iterations: Optional[int] = None
    ) -> AgentResult:
        """
        Main execution loop with plan/act/reflect pattern.

        Iterates until confidence threshold is met or max iterations reached.

        Args:
            goal: The objective to achieve.
            context: Initial context.
            max_iterations: Override instance max_iterations.

        Returns:
            Final AgentResult (best effort if max iterations reached).
        """
        iterations = max_iterations or self.max_iterations
        self._iteration_count = 0
        current_context = context.copy()
        best_result: Optional[AgentResult] = None

        logger.info(f"Agent '{self.name}' starting run with goal: {goal[:100]}...")

        for i in range(iterations):
            self._iteration_count = i + 1

            logger.debug(f"Agent '{self.name}' iteration {self._iteration_count}/{iterations}")

            # Plan
            try:
                plan = await self.plan(goal, current_context)
                if self.scratchpad:
                    self.scratchpad.append_plan(self.name, plan.to_dict())
            except Exception as e:
                logger.error(f"Agent '{self.name}' planning failed: {e}")
                return AgentResult(
                    agent_name=self.name,
                    success=False,
                    data={},
                    confidence=0.0,
                    errors=[f"Planning failed: {str(e)}"]
                )

            # Act
            try:
                result = await self.act(plan)
                best_result = result  # Track best result

                if self.scratchpad:
                    self.scratchpad.append_result(self.name, result.to_dict())
            except Exception as e:
                logger.error(f"Agent '{self.name}' action failed: {e}")
                return AgentResult(
                    agent_name=self.name,
                    success=False,
                    data={},
                    confidence=0.0,
                    errors=[f"Action failed: {str(e)}"]
                )

            # Reflect
            try:
                reflection = await self.reflect(result)

                if self.scratchpad:
                    self.scratchpad.append_reflection(self.name, reflection.to_dict())

                # Check if we're done
                if reflection.confidence >= self.confidence_threshold and not reflection.needs_retry:
                    logger.info(
                        f"Agent '{self.name}' completed in {self._iteration_count} iteration(s) "
                        f"with confidence {reflection.confidence:.2f}"
                    )
                    return result

                # Update context for retry
                current_context = self._update_context(current_context, reflection)

                logger.info(
                    f"Agent '{self.name}' iteration {self._iteration_count}: "
                    f"confidence={reflection.confidence:.2f}, needs_retry={reflection.needs_retry}, "
                    f"gaps={len(reflection.gaps_identified)}"
                )

            except Exception as e:
                logger.error(f"Agent '{self.name}' reflection failed: {e}")
                # Return best result so far
                if best_result:
                    best_result.warnings.append(f"Reflection failed: {str(e)}")
                    return best_result
                return AgentResult(
                    agent_name=self.name,
                    success=False,
                    data={},
                    confidence=0.0,
                    errors=[f"Reflection failed: {str(e)}"]
                )

        # Max iterations reached
        logger.warning(
            f"Agent '{self.name}' reached max iterations ({iterations}), "
            f"returning best result with confidence {best_result.confidence if best_result else 0:.2f}"
        )

        if best_result:
            best_result.warnings.append(f"Max iterations ({iterations}) reached")
            return best_result

        return AgentResult(
            agent_name=self.name,
            success=False,
            data={},
            confidence=0.0,
            errors=["No result produced after all iterations"]
        )

    async def invoke_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke a tool from the agent's available tools.

        Override in subclasses to implement actual tool execution.

        Args:
            tool_name: Name of the tool to invoke.
            params: Parameters for the tool.

        Returns:
            Tool execution result.

        Raises:
            ValueError: If tool is not available to this agent.
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not available to agent '{self.name}'")

        logger.debug(f"Agent '{self.name}' invoking tool '{tool_name}'")
        # Subclasses implement actual tool execution
        return {"status": "not_implemented", "tool": tool_name}

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"tools={self.tools}, "
            f"threshold={self.confidence_threshold})"
        )
