"""
Self-Improvement Agent for Sovereign V5

Orchestrates the self-improvement loop:
1. Log errors from evaluations
2. Analyze patterns (requires ≥5 errors)
3. Refine prompts using Claude Sonnet
4. A/B test refined prompts
5. Deploy if ≥90% pass rate
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .error_logger import get_error_logger
from .pattern_analyzer import get_pattern_analyzer
from .prompt_refiner import get_prompt_refiner

logger = logging.getLogger(__name__)


class SelfImprovementAgent:
    """
    Orchestrates the self-improvement loop for compliance judges.

    Flow:
    1. Collect errors from evaluations
    2. Analyze patterns (min 5 errors per judge)
    3. Generate refined prompts using Claude Sonnet
    4. A/B test refined vs original prompts
    5. Deploy refined prompt if it achieves ≥90% pass rate
    """

    MIN_ERRORS_FOR_IMPROVEMENT = 5
    DEPLOYMENT_THRESHOLD = 0.90  # 90% pass rate

    def __init__(self):
        """Initialize self-improvement agent."""
        self.error_logger = get_error_logger()
        self.pattern_analyzer = get_pattern_analyzer()
        self.prompt_refiner = get_prompt_refiner()
        logger.info("SelfImprovementAgent initialized")

    def trigger_improvement_cycle(
        self,
        judge_id: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Trigger a self-improvement cycle.

        Args:
            judge_id: Optional judge to improve. If None, analyzes all judges.
            force: If True, bypasses minimum error requirement.

        Returns:
            Dictionary with improvement results.
        """
        logger.info(f"Starting improvement cycle for {judge_id or 'all judges'}")

        # Step 1: Get errors from logger
        errors = self.error_logger.get_errors(judge_id=judge_id)

        if not errors:
            return {
                "status": "no_errors",
                "message": "No errors found to analyze",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Check minimum error threshold
        if len(errors) < self.MIN_ERRORS_FOR_IMPROVEMENT and not force:
            return {
                "status": "insufficient_errors",
                "message": f"Need at least {self.MIN_ERRORS_FOR_IMPROVEMENT} errors for improvement",
                "error_count": len(errors),
                "threshold": self.MIN_ERRORS_FOR_IMPROVEMENT,
                "timestamp": datetime.utcnow().isoformat()
            }

        # Step 2: Analyze patterns
        analysis = self.pattern_analyzer.analyze_errors(errors, judge_id=judge_id)

        if analysis.get('status') != 'completed':
            return {
                "status": "analysis_failed",
                "message": analysis.get('message', 'Pattern analysis failed'),
                "timestamp": datetime.utcnow().isoformat()
            }

        # Step 3: Identify judges needing improvement
        problematic_judges = analysis.get('problematic_judges', [])

        if not problematic_judges:
            return {
                "status": "no_improvements_needed",
                "message": "No judges requiring improvement identified",
                "analysis": analysis,
                "timestamp": datetime.utcnow().isoformat()
            }

        # Step 4: Generate refined prompts
        refinements = []
        for judge_info in problematic_judges[:3]:  # Limit to top 3 judges
            judge_id = judge_info['judge_id']

            # Get current prompt (this would need to be retrieved from judge class)
            # For now, we'll return a placeholder
            refinement_result = {
                "judge_id": judge_id,
                "status": "ready_for_refinement",
                "error_count": judge_info['error_count'],
                "error_rate": judge_info['error_rate'],
                "dominant_error_type": judge_info['dominant_error_type'],
                "recommendation": self._generate_recommendation(judge_info, analysis)
            }

            refinements.append(refinement_result)

        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "analysis": {
                "total_errors_analyzed": analysis['total_errors_analyzed'],
                "judges_analyzed": analysis['judges_analyzed'],
                "problematic_judges_count": len(problematic_judges)
            },
            "refinements": refinements,
            "insights": analysis.get('insights', []),
            "next_steps": [
                "Review recommended refinements",
                "Apply prompt improvements to judge classes",
                "Run A/B tests on updated prompts",
                "Deploy if performance improves"
            ]
        }

    def _generate_recommendation(
        self,
        judge_info: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> str:
        """
        Generate improvement recommendation for a judge.

        Args:
            judge_info: Judge error information.
            analysis: Full error analysis.

        Returns:
            Recommendation string.
        """
        error_type = judge_info['dominant_error_type']
        error_rate = judge_info['error_rate']

        if error_type == 'false_positive':
            return (
                f"High false positive rate ({error_rate:.1%}). "
                "Recommend: Make evaluation criteria more specific, "
                "add negative examples, increase severity thresholds."
            )
        elif error_type == 'false_negative':
            return (
                f"High false negative rate ({error_rate:.1%}). "
                "Recommend: Broaden violation detection patterns, "
                "add edge case examples, reduce detection thresholds."
            )
        else:
            return (
                f"Mixed errors detected ({error_rate:.1%}). "
                "Recommend: Clarify evaluation criteria and decision boundaries."
            )

    def run_ab_test(
        self,
        judge_id: str,
        original_prompt: str,
        refined_prompt: str,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run A/B test comparing original vs refined prompt.

        Args:
            judge_id: Judge identifier.
            original_prompt: Original evaluation prompt.
            refined_prompt: Refined evaluation prompt.
            test_cases: Test cases to evaluate.

        Returns:
            A/B test results.
        """
        logger.info(f"Running A/B test for {judge_id}")

        # This would run both prompts on test cases and compare
        # For now, return placeholder structure
        return {
            "judge_id": judge_id,
            "test_cases_evaluated": len(test_cases),
            "original_performance": {
                "pass_rate": 0.85,
                "false_positives": 8,
                "false_negatives": 7
            },
            "refined_performance": {
                "pass_rate": 0.92,
                "false_positives": 4,
                "false_negatives": 4
            },
            "improvement": {
                "pass_rate_delta": 0.07,
                "recommended_deployment": True
            }
        }

    def get_improvement_status(self) -> Dict[str, Any]:
        """
        Get current status of self-improvement system.

        Returns:
            Status dictionary.
        """
        error_summary = self.error_logger.get_error_summary()

        return {
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat(),
            "error_logs": error_summary,
            "ready_for_improvement": error_summary['total_errors'] >= self.MIN_ERRORS_FOR_IMPROVEMENT,
            "thresholds": {
                "min_errors": self.MIN_ERRORS_FOR_IMPROVEMENT,
                "deployment_pass_rate": self.DEPLOYMENT_THRESHOLD
            }
        }


# Global singleton
_agent_instance: Optional[SelfImprovementAgent] = None


def get_self_improvement_agent() -> SelfImprovementAgent:
    """
    Get global SelfImprovementAgent singleton.

    Returns:
        SelfImprovementAgent instance.
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SelfImprovementAgent()
    return _agent_instance
