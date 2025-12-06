"""
Pattern Analyzer for Sovereign V5 Self-Improvement

Analyzes error patterns to identify systematic issues in judge prompts.
Requires minimum of 5 errors before suggesting improvements.
"""

import logging
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """
    Analyzes error patterns to identify improvement opportunities.

    Looks for:
    - High false positive/negative rates for specific judges
    - Common phrases or patterns in misclassified submissions
    - Systematic issues across frameworks
    """

    MIN_ERRORS_FOR_ANALYSIS = 5

    def __init__(self):
        """Initialize pattern analyzer."""
        logger.info("PatternAnalyzer initialized")

    def analyze_errors(
        self,
        errors: List[Dict[str, Any]],
        judge_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze error patterns.

        Args:
            errors: List of error log dictionaries.
            judge_id: Optional judge ID to focus analysis on.

        Returns:
            Dictionary with analysis results.
        """
        if not errors:
            return {
                "status": "no_errors",
                "message": "No errors to analyze"
            }

        if len(errors) < self.MIN_ERRORS_FOR_ANALYSIS:
            return {
                "status": "insufficient_data",
                "message": f"Need at least {self.MIN_ERRORS_FOR_ANALYSIS} errors for analysis",
                "error_count": len(errors)
            }

        # Filter by judge if specified
        if judge_id:
            errors = [e for e in errors if e.get('judge_id') == judge_id]

        if not errors:
            return {
                "status": "no_errors",
                "message": f"No errors for judge {judge_id}"
            }

        # Analyze error types
        error_types = Counter(e.get('error_type') for e in errors)

        # Analyze by judge
        errors_by_judge = defaultdict(list)
        for error in errors:
            errors_by_judge[error.get('judge_id', 'unknown')].append(error)

        # Analyze false positives vs false negatives
        false_positives = [e for e in errors if e.get('error_type') == 'false_positive']
        false_negatives = [e for e in errors if e.get('error_type') == 'false_negative']

        # Extract common patterns in submissions
        patterns = self._extract_submission_patterns(errors)

        # Identify problematic judges
        problematic_judges = []
        for judge_id, judge_errors in errors_by_judge.items():
            if len(judge_errors) >= self.MIN_ERRORS_FOR_ANALYSIS:
                error_rate = len(judge_errors) / len(errors)
                problematic_judges.append({
                    "judge_id": judge_id,
                    "error_count": len(judge_errors),
                    "error_rate": round(error_rate, 3),
                    "dominant_error_type": Counter(
                        e.get('error_type') for e in judge_errors
                    ).most_common(1)[0][0]
                })

        # Sort by error count
        problematic_judges.sort(key=lambda x: x['error_count'], reverse=True)

        # Generate insights
        insights = self._generate_insights(
            errors=errors,
            error_types=error_types,
            false_positives=false_positives,
            false_negatives=false_negatives,
            problematic_judges=problematic_judges
        )

        return {
            "status": "completed",
            "total_errors_analyzed": len(errors),
            "error_type_distribution": dict(error_types),
            "false_positive_count": len(false_positives),
            "false_negative_count": len(false_negatives),
            "judges_analyzed": len(errors_by_judge),
            "problematic_judges": problematic_judges,
            "submission_patterns": patterns,
            "insights": insights,
            "ready_for_refinement": len(errors) >= self.MIN_ERRORS_FOR_ANALYSIS
        }

    def _extract_submission_patterns(
        self,
        errors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract common patterns in error submissions.

        Args:
            errors: List of errors.

        Returns:
            Dictionary with pattern information.
        """
        # Extract common words in false positives vs false negatives
        false_positive_texts = [
            e.get('submission_text', '')
            for e in errors
            if e.get('error_type') == 'false_positive'
        ]

        false_negative_texts = [
            e.get('submission_text', '')
            for e in errors
            if e.get('error_type') == 'false_negative'
        ]

        # Find common keywords
        fp_keywords = self._extract_keywords(false_positive_texts)
        fn_keywords = self._extract_keywords(false_negative_texts)

        return {
            "false_positive_keywords": fp_keywords[:10],
            "false_negative_keywords": fn_keywords[:10],
            "avg_submission_length": {
                "false_positives": sum(len(t) for t in false_positive_texts) / len(false_positive_texts) if false_positive_texts else 0,
                "false_negatives": sum(len(t) for t in false_negative_texts) / len(false_negative_texts) if false_negative_texts else 0
            }
        }

    def _extract_keywords(self, texts: List[str], top_n: int = 10) -> List[str]:
        """
        Extract common keywords from texts.

        Args:
            texts: List of text strings.
            top_n: Number of top keywords to return.

        Returns:
            List of common keywords.
        """
        if not texts:
            return []

        # Simple keyword extraction (word frequency)
        # Filter out common stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
            'can', 'could', 'may', 'might', 'must', 'shall'
        }

        words = []
        for text in texts:
            # Simple tokenization
            tokens = text.lower().split()
            words.extend([
                w.strip('.,!?;:"()[]{}')
                for w in tokens
                if w.lower() not in stopwords and len(w) > 3
            ])

        # Count and return most common
        counter = Counter(words)
        return [word for word, count in counter.most_common(top_n)]

    def _generate_insights(
        self,
        errors: List[Dict[str, Any]],
        error_types: Counter,
        false_positives: List[Dict[str, Any]],
        false_negatives: List[Dict[str, Any]],
        problematic_judges: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate actionable insights from analysis.

        Args:
            errors: All errors.
            error_types: Error type distribution.
            false_positives: False positive errors.
            false_negatives: False negative errors.
            problematic_judges: List of judges with high error rates.

        Returns:
            List of insight strings.
        """
        insights = []

        # Check for bias toward false positives or negatives
        if len(false_positives) > len(false_negatives) * 2:
            insights.append(
                f"High false positive rate ({len(false_positives)} vs {len(false_negatives)} FN). "
                "Consider making judge prompts more conservative."
            )
        elif len(false_negatives) > len(false_positives) * 2:
            insights.append(
                f"High false negative rate ({len(false_negatives)} vs {len(false_positives)} FP). "
                "Consider making judge prompts more sensitive to violations."
            )

        # Identify judges needing attention
        if problematic_judges:
            top_judge = problematic_judges[0]
            insights.append(
                f"Judge '{top_judge['judge_id']}' has highest error rate with "
                f"{top_judge['error_count']} errors ({top_judge['error_rate']:.1%}). "
                f"Primary issue: {top_judge['dominant_error_type']}."
            )

        # Check for systematic issues
        if len(problematic_judges) >= 3:
            insights.append(
                f"{len(problematic_judges)} judges showing systematic errors. "
                "Consider reviewing evaluation methodology or test dataset quality."
            )

        # Confidence-related insights
        low_confidence_errors = [
            e for e in errors
            if e.get('confidence') is not None and e.get('confidence') < 0.5
        ]
        if low_confidence_errors:
            insights.append(
                f"{len(low_confidence_errors)} errors involved low confidence predictions. "
                "Consider refining prompts to improve decision clarity."
            )

        return insights


# Global singleton
_analyzer_instance: Optional[PatternAnalyzer] = None


def get_pattern_analyzer() -> PatternAnalyzer:
    """
    Get global PatternAnalyzer singleton.

    Returns:
        PatternAnalyzer instance.
    """
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = PatternAnalyzer()
    return _analyzer_instance
