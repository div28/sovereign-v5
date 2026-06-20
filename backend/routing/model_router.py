"""
Model Router for Sovereign V5

Intelligently routes framework evaluations to appropriate Claude models:
- GDPR → Haiku (fast, cost-effective)
- SOX → Haiku (structured compliance)
- EU AI Act → Sonnet (complex regulatory reasoning)

Tracks token usage and calculates cost savings vs all-Sonnet baseline.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


# Anthropic pricing (as of June 2026)
# Prices per million tokens
PRICING = {
    "claude-sonnet-4-20250514": {
        "input": 3.00,   # $3 per million input tokens
        "output": 15.00  # $15 per million output tokens
    },
    "claude-3-5-haiku-20241022": {
        "input": 1.00,   # $1 per million input tokens
        "output": 5.00   # $5 per million output tokens
    }
}


@dataclass
class UsageStats:
    """Track usage statistics for a model."""
    input_tokens: int = 0
    output_tokens: int = 0
    call_count: int = 0
    total_cost: float = 0.0


@dataclass
class RoutingDecision:
    """Represents a model routing decision."""
    framework: str
    model: str
    reasoning: str


class ModelRouter:
    """
    Intelligent model router for compliance evaluations.

    Routes frameworks to models based on complexity:
    - GDPR: Haiku (straightforward regulatory checks)
    - SOX: Haiku (structured compliance requirements)
    - EU AI Act: Sonnet (complex AI governance reasoning)
    """

    # Framework to model mapping - ALL USE SONNET 4 FOR BETTER ACCURACY
    FRAMEWORK_MODEL_MAP = {
        "gdpr": "claude-sonnet-4-20250514",
        "sox": "claude-sonnet-4-20250514",
        "euai": "claude-sonnet-4-20250514"
    }

    def __init__(self):
        """Initialize the model router."""
        self._usage_stats: Dict[str, UsageStats] = {}
        self._lock = Lock()
        logger.info("ModelRouter initialized with framework mapping")

    def route(self, framework: str) -> RoutingDecision:
        """
        Route a framework evaluation to the appropriate model.

        Args:
            framework: Framework identifier (gdpr, sox, euai).

        Returns:
            RoutingDecision with model and reasoning.
        """
        framework_lower = framework.lower()

        # Get model from mapping
        model = self.FRAMEWORK_MODEL_MAP.get(
            framework_lower,
            "claude-sonnet-4-20250514"  # Default to Sonnet 4
        )

        # Provide reasoning for the routing decision
        reasoning_map = {
            "gdpr": "GDPR articles have clear, structured requirements suitable for Haiku",
            "sox": "SOX sections are well-defined compliance checks suitable for Haiku",
            "euai": "EU AI Act requires complex reasoning about AI systems, using Sonnet"
        }

        reasoning = reasoning_map.get(
            framework_lower,
            "Using default model for unknown framework"
        )

        decision = RoutingDecision(
            framework=framework,
            model=model,
            reasoning=reasoning
        )

        logger.debug(f"Routed {framework} to {model}: {reasoning}")
        return decision

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ):
        """
        Record token usage for a model call.

        Args:
            model: Model identifier.
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens used.
        """
        with self._lock:
            if model not in self._usage_stats:
                self._usage_stats[model] = UsageStats()

            stats = self._usage_stats[model]
            stats.input_tokens += input_tokens
            stats.output_tokens += output_tokens
            stats.call_count += 1

            # Calculate cost for this call
            if model in PRICING:
                input_cost = (input_tokens / 1_000_000) * PRICING[model]["input"]
                output_cost = (output_tokens / 1_000_000) * PRICING[model]["output"]
                stats.total_cost += input_cost + output_cost

            logger.debug(
                f"Recorded usage for {model}: "
                f"{input_tokens} in, {output_tokens} out"
            )

    def get_usage_stats(self, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get usage statistics.

        Args:
            model: Optional model to get stats for. If None, returns all.

        Returns:
            Dictionary of usage statistics.
        """
        with self._lock:
            if model:
                if model not in self._usage_stats:
                    return {
                        "model": model,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "call_count": 0,
                        "total_cost": 0.0
                    }

                stats = self._usage_stats[model]
                return {
                    "model": model,
                    "input_tokens": stats.input_tokens,
                    "output_tokens": stats.output_tokens,
                    "call_count": stats.call_count,
                    "total_cost": round(stats.total_cost, 4)
                }

            # Return all stats
            return {
                model: {
                    "input_tokens": stats.input_tokens,
                    "output_tokens": stats.output_tokens,
                    "call_count": stats.call_count,
                    "total_cost": round(stats.total_cost, 4)
                }
                for model, stats in self._usage_stats.items()
            }

    def get_cost_summary(self) -> Dict[str, Any]:
        """
        Get cost summary including savings vs all-Sonnet baseline.

        Returns:
            Dictionary with cost analysis:
            - actual_cost: Cost using intelligent routing
            - baseline_cost: Cost if all calls used Sonnet
            - savings: Difference
            - savings_percentage: Percentage saved
        """
        with self._lock:
            # Calculate actual cost
            actual_cost = sum(
                stats.total_cost
                for stats in self._usage_stats.values()
            )

            # Calculate total tokens
            total_input_tokens = sum(
                stats.input_tokens
                for stats in self._usage_stats.values()
            )
            total_output_tokens = sum(
                stats.output_tokens
                for stats in self._usage_stats.values()
            )

            # Calculate baseline cost (if everything used Sonnet)
            sonnet_model = "claude-sonnet-4-20250514"
            baseline_input_cost = (total_input_tokens / 1_000_000) * PRICING[sonnet_model]["input"]
            baseline_output_cost = (total_output_tokens / 1_000_000) * PRICING[sonnet_model]["output"]
            baseline_cost = baseline_input_cost + baseline_output_cost

            # Calculate savings
            savings = baseline_cost - actual_cost
            savings_percentage = (savings / baseline_cost * 100) if baseline_cost > 0 else 0

            # Get per-model breakdown
            model_breakdown = {}
            for model, stats in self._usage_stats.items():
                model_breakdown[model] = {
                    "calls": stats.call_count,
                    "input_tokens": stats.input_tokens,
                    "output_tokens": stats.output_tokens,
                    "cost": round(stats.total_cost, 4)
                }

            return {
                "actual_cost": round(actual_cost, 4),
                "baseline_cost": round(baseline_cost, 4),
                "savings": round(savings, 4),
                "savings_percentage": round(savings_percentage, 2),
                "total_calls": sum(stats.call_count for stats in self._usage_stats.values()),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "model_breakdown": model_breakdown
            }

    def reset_stats(self):
        """Reset all usage statistics."""
        with self._lock:
            self._usage_stats.clear()
            logger.info("Usage statistics reset")

    def get_model_for_framework(self, framework: str) -> str:
        """
        Get the model that should be used for a framework.

        Args:
            framework: Framework identifier.

        Returns:
            Model identifier string.
        """
        decision = self.route(framework)
        return decision.model


# Global singleton instance
_router_instance: Optional[ModelRouter] = None
_router_lock = Lock()


def get_model_router() -> ModelRouter:
    """
    Get the global ModelRouter singleton instance.

    Returns:
        ModelRouter instance.
    """
    global _router_instance

    if _router_instance is None:
        with _router_lock:
            # Double-check locking
            if _router_instance is None:
                _router_instance = ModelRouter()
                logger.info("Created global ModelRouter instance")

    return _router_instance
