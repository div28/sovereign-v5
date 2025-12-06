"""
Evaluation Metrics for Sovereign V5

Calculates performance metrics for compliance judges:
- TPR (True Positive Rate / Recall)
- TNR (True Negative Rate / Specificity)
- F1 Score
- Confusion Matrix
- Critical Case Recall
"""

import logging
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfusionMatrix:
    """Confusion matrix for binary classification."""
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def total(self) -> int:
        """Total number of predictions."""
        return self.true_positives + self.true_negatives + self.false_positives + self.false_negatives

    @property
    def tpr(self) -> float:
        """True Positive Rate (Recall/Sensitivity)."""
        denominator = self.true_positives + self.false_negatives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def tnr(self) -> float:
        """True Negative Rate (Specificity)."""
        denominator = self.true_negatives + self.false_positives
        if denominator == 0:
            return 0.0
        return self.true_negatives / denominator

    @property
    def fpr(self) -> float:
        """False Positive Rate."""
        return 1.0 - self.tnr

    @property
    def fnr(self) -> float:
        """False Negative Rate."""
        return 1.0 - self.tpr

    @property
    def precision(self) -> float:
        """Precision (Positive Predictive Value)."""
        denominator = self.true_positives + self.false_positives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def f1_score(self) -> float:
        """F1 Score (harmonic mean of precision and recall)."""
        precision = self.precision
        recall = self.tpr
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    @property
    def accuracy(self) -> float:
        """Overall accuracy."""
        if self.total == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / self.total

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "confusion_matrix": {
                "true_positives": self.true_positives,
                "true_negatives": self.true_negatives,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
                "total": self.total
            },
            "metrics": {
                "tpr": round(self.tpr, 4),
                "tnr": round(self.tnr, 4),
                "fpr": round(self.fpr, 4),
                "fnr": round(self.fnr, 4),
                "precision": round(self.precision, 4),
                "f1_score": round(self.f1_score, 4),
                "accuracy": round(self.accuracy, 4)
            }
        }


@dataclass
class EvaluationMetrics:
    """Complete evaluation metrics for a judge or set of judges."""
    judge_id: str
    confusion_matrix: ConfusionMatrix
    critical_case_recall: float
    test_cases_evaluated: int
    critical_cases_total: int
    critical_cases_detected: int

    def meets_targets(
        self,
        min_tpr: float = 0.90,
        min_tnr: float = 0.90,
        min_critical_recall: float = 0.95
    ) -> bool:
        """
        Check if metrics meet target thresholds.

        Args:
            min_tpr: Minimum acceptable TPR (default 90%).
            min_tnr: Minimum acceptable TNR (default 90%).
            min_critical_recall: Minimum critical case recall (default 95%).

        Returns:
            True if all targets met.
        """
        return (
            self.confusion_matrix.tpr >= min_tpr and
            self.confusion_matrix.tnr >= min_tnr and
            self.critical_case_recall >= min_critical_recall
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "judge_id": self.judge_id,
            "test_cases_evaluated": self.test_cases_evaluated,
            "confusion_matrix": self.confusion_matrix.confusion_matrix,
            "metrics": self.confusion_matrix.metrics,
            "critical_cases": {
                "total": self.critical_cases_total,
                "detected": self.critical_cases_detected,
                "recall": round(self.critical_case_recall, 4)
            },
            "targets_met": self.meets_targets()
        }


def calculate_confusion_matrix(
    predictions: List[bool],
    ground_truth: List[bool]
) -> ConfusionMatrix:
    """
    Calculate confusion matrix from predictions and ground truth.

    Args:
        predictions: List of predicted violation flags (True = violation detected).
        ground_truth: List of actual violation flags (True = violation exists).

    Returns:
        ConfusionMatrix object.
    """
    if len(predictions) != len(ground_truth):
        raise ValueError("Predictions and ground truth must have same length")

    cm = ConfusionMatrix()

    for pred, truth in zip(predictions, ground_truth):
        if pred and truth:
            cm.true_positives += 1
        elif not pred and not truth:
            cm.true_negatives += 1
        elif pred and not truth:
            cm.false_positives += 1
        else:  # not pred and truth
            cm.false_negatives += 1

    return cm


def calculate_critical_case_recall(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]]
) -> Tuple[float, int, int]:
    """
    Calculate recall specifically for critical cases.

    Args:
        predictions: List of prediction results with severity info.
        ground_truth: List of ground truth cases with severity info.

    Returns:
        Tuple of (critical_recall, critical_detected, critical_total).
    """
    # Find critical cases in ground truth
    critical_indices = [
        i for i, case in enumerate(ground_truth)
        if case.get('severity') == 'CRITICAL'
    ]

    if not critical_indices:
        return 1.0, 0, 0  # No critical cases, perfect recall

    # Check how many critical cases were detected
    critical_detected = sum(
        1 for i in critical_indices
        if i < len(predictions) and predictions[i].get('violation_detected', False)
    )

    critical_total = len(critical_indices)
    recall = critical_detected / critical_total if critical_total > 0 else 0.0

    return recall, critical_detected, critical_total


def evaluate_judge_performance(
    judge_results: List[Dict[str, Any]],
    golden_dataset: List[Dict[str, Any]],
    judge_id: str
) -> EvaluationMetrics:
    """
    Evaluate a judge's performance against golden dataset.

    Args:
        judge_results: List of judge evaluation results.
        golden_dataset: Golden dataset with ground truth.
        judge_id: Identifier for the judge.

    Returns:
        EvaluationMetrics object.
    """
    if len(judge_results) != len(golden_dataset):
        logger.warning(
            f"Judge results ({len(judge_results)}) and golden dataset "
            f"({len(golden_dataset)}) have different lengths"
        )

    # Extract predictions and ground truth
    predictions = [
        result.get('violation_detected', False)
        for result in judge_results
    ]

    ground_truth = [
        case.get('expected_violation', False)
        for case in golden_dataset
    ]

    # Calculate confusion matrix
    cm = calculate_confusion_matrix(predictions, ground_truth)

    # Calculate critical case recall
    critical_recall, critical_detected, critical_total = calculate_critical_case_recall(
        judge_results,
        golden_dataset
    )

    metrics = EvaluationMetrics(
        judge_id=judge_id,
        confusion_matrix=cm,
        critical_case_recall=critical_recall,
        test_cases_evaluated=len(judge_results),
        critical_cases_total=critical_total,
        critical_cases_detected=critical_detected
    )

    logger.info(
        f"{judge_id} metrics: TPR={cm.tpr:.2%}, TNR={cm.tnr:.2%}, "
        f"F1={cm.f1_score:.2%}, Critical Recall={critical_recall:.2%}"
    )

    return metrics


def aggregate_metrics(metrics_list: List[EvaluationMetrics]) -> Dict[str, Any]:
    """
    Aggregate metrics across multiple judges.

    Args:
        metrics_list: List of EvaluationMetrics for different judges.

    Returns:
        Dictionary with aggregated metrics.
    """
    if not metrics_list:
        return {}

    # Sum up confusion matrices
    total_cm = ConfusionMatrix()
    total_critical_detected = 0
    total_critical_cases = 0

    for metrics in metrics_list:
        cm = metrics.confusion_matrix
        total_cm.true_positives += cm.true_positives
        total_cm.true_negatives += cm.true_negatives
        total_cm.false_positives += cm.false_positives
        total_cm.false_negatives += cm.false_negatives

        total_critical_detected += metrics.critical_cases_detected
        total_critical_cases += metrics.critical_cases_total

    # Calculate aggregate critical recall
    aggregate_critical_recall = (
        total_critical_detected / total_critical_cases
        if total_critical_cases > 0 else 0.0
    )

    return {
        "aggregate_metrics": total_cm.to_dict(),
        "critical_case_recall": round(aggregate_critical_recall, 4),
        "total_judges": len(metrics_list),
        "total_test_cases": sum(m.test_cases_evaluated for m in metrics_list),
        "judges_meeting_targets": sum(1 for m in metrics_list if m.meets_targets()),
        "targets_met": all(m.meets_targets() for m in metrics_list)
    }
