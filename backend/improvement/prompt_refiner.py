"""
Prompt Refiner for Sovereign V5 Self-Improvement

Uses Claude Sonnet to refine judge prompts based on error patterns.
Generates improved prompts that address systematic failures.
"""

import os
import logging
from typing import Dict, List, Any, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)


class PromptRefiner:
    """
    Refines judge prompts using Claude Sonnet based on error analysis.

    Takes error patterns and generates improved prompt versions
    that address identified weaknesses.
    """

    REFINEMENT_PROMPT_TEMPLATE = """You are a prompt engineering expert specializing in regulatory compliance evaluation.

Your task is to refine an AI judge prompt that is making systematic errors in compliance evaluations.

## Current Judge Information

**Judge ID:** {judge_id}
**Framework:** {framework}
**Focus Area:** {focus_area}

## Current Prompt

{current_prompt}

## Error Analysis

**Total Errors:** {total_errors}
**False Positives:** {false_positives}
**False Negatives:** {false_negatives}
**Dominant Error Type:** {dominant_error_type}

## Error Patterns

{error_patterns}

## Your Task

Refine the current prompt to address these errors while maintaining:
1. Accuracy and precision in detecting violations
2. Clear evaluation criteria
3. Appropriate severity classification
4. Professional regulatory language

Focus on:
- Reducing {dominant_error_type} errors
- Improving decision boundaries
- Adding clarifying examples if needed
- Enhancing specificity where errors occur

Provide the refined prompt that can directly replace the current EVALUATION_PROMPT.
Keep the same structure with {{regulatory_context}} and {{submission}} placeholders.
"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize prompt refiner.

        Args:
            api_key: Anthropic API key.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        self._client = Anthropic(api_key=self.api_key)
        logger.info("PromptRefiner initialized")

    def refine_prompt(
        self,
        judge_id: str,
        framework: str,
        focus_area: str,
        current_prompt: str,
        error_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate refined prompt based on error analysis.

        Args:
            judge_id: Judge identifier.
            framework: Regulatory framework.
            focus_area: Judge focus area.
            current_prompt: Current evaluation prompt.
            error_analysis: Error analysis results.

        Returns:
            Dictionary with refined prompt and metadata.
        """
        # Extract key metrics from analysis
        total_errors = error_analysis.get('total_errors_analyzed', 0)
        false_positives = error_analysis.get('false_positive_count', 0)
        false_negatives = error_analysis.get('false_negative_count', 0)

        # Determine dominant error type
        if false_positives > false_negatives:
            dominant_error_type = "false_positive"
        else:
            dominant_error_type = "false_negative"

        # Format error patterns
        insights = error_analysis.get('insights', [])
        patterns = error_analysis.get('submission_patterns', {})

        error_patterns = self._format_error_patterns(insights, patterns, dominant_error_type)

        # Build refinement prompt
        refinement_prompt = self.REFINEMENT_PROMPT_TEMPLATE.format(
            judge_id=judge_id,
            framework=framework,
            focus_area=focus_area,
            current_prompt=current_prompt,
            total_errors=total_errors,
            false_positives=false_positives,
            false_negatives=false_negatives,
            dominant_error_type=dominant_error_type.replace('_', ' '),
            error_patterns=error_patterns
        )

        try:
            # Use Claude Sonnet for prompt refinement
            response = self._client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": refinement_prompt
                }]
            )

            # Extract refined prompt
            refined_prompt = response.content[0].text

            logger.info(f"Generated refined prompt for {judge_id}")

            return {
                "status": "success",
                "judge_id": judge_id,
                "original_prompt": current_prompt,
                "refined_prompt": refined_prompt,
                "error_analysis_summary": {
                    "total_errors": total_errors,
                    "false_positives": false_positives,
                    "false_negatives": false_negatives,
                    "dominant_error_type": dominant_error_type
                },
                "tokens_used": {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens
                }
            }

        except Exception as e:
            logger.error(f"Failed to refine prompt for {judge_id}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "judge_id": judge_id
            }

    def _format_error_patterns(
        self,
        insights: List[str],
        patterns: Dict[str, Any],
        dominant_error_type: str
    ) -> str:
        """
        Format error patterns for prompt.

        Args:
            insights: List of insight strings.
            patterns: Pattern analysis results.
            dominant_error_type: Dominant error type.

        Returns:
            Formatted string.
        """
        formatted = []

        # Add insights
        if insights:
            formatted.append("**Key Insights:**")
            for insight in insights:
                formatted.append(f"- {insight}")
            formatted.append("")

        # Add submission patterns
        if dominant_error_type == "false_positive":
            keywords = patterns.get('false_positive_keywords', [])
            if keywords:
                formatted.append("**Common terms in false positive submissions:**")
                formatted.append(", ".join(keywords))
                formatted.append("")
                formatted.append(
                    "These terms may be triggering false alarms. "
                    "Refine the prompt to be more specific about actual violations."
                )
        else:
            keywords = patterns.get('false_negative_keywords', [])
            if keywords:
                formatted.append("**Common terms in missed violations:**")
                formatted.append(", ".join(keywords))
                formatted.append("")
                formatted.append(
                    "These submissions contain violations that were missed. "
                    "Refine the prompt to better detect these patterns."
                )

        return "\n".join(formatted)

    def batch_refine(
        self,
        refinement_requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Refine multiple judge prompts in batch.

        Args:
            refinement_requests: List of refinement request dicts with:
                - judge_id
                - framework
                - focus_area
                - current_prompt
                - error_analysis

        Returns:
            List of refinement results.
        """
        results = []

        for request in refinement_requests:
            result = self.refine_prompt(
                judge_id=request['judge_id'],
                framework=request['framework'],
                focus_area=request['focus_area'],
                current_prompt=request['current_prompt'],
                error_analysis=request['error_analysis']
            )
            results.append(result)

        logger.info(f"Completed batch refinement of {len(results)} prompts")
        return results


# Global singleton
_refiner_instance: Optional[PromptRefiner] = None


def get_prompt_refiner() -> PromptRefiner:
    """
    Get global PromptRefiner singleton.

    Returns:
        PromptRefiner instance.
    """
    global _refiner_instance
    if _refiner_instance is None:
        _refiner_instance = PromptRefiner()
    return _refiner_instance
