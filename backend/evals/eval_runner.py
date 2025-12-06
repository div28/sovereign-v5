"""
Evaluation Runner for Sovereign V5

Executes all 9 judges against golden dataset and calculates performance metrics.
Target thresholds: TPR≥90%, TNR≥90%, Critical TPR≥95%
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .eval_metrics import evaluate_judge_performance, aggregate_metrics, EvaluationMetrics

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """
    Runs compliance judges against golden dataset for evaluation.

    The golden dataset should be structured as:
    [
        {
            "test_id": "gdpr_001",
            "description": "System description to test",
            "framework": "gdpr",
            "judge_id": "gdpr_automated_decision_making",
            "expected_violation": true,
            "severity": "CRITICAL",
            "article": "Article 22",
            "notes": "Test case for automated decision-making"
        },
        ...
    ]
    """

    def __init__(
        self,
        golden_dataset_path: str = "data/golden_dataset.json",
        max_workers: int = 9
    ):
        """
        Initialize evaluation runner.

        Args:
            golden_dataset_path: Path to golden dataset JSON file.
            max_workers: Maximum parallel workers for evaluation.
        """
        self.golden_dataset_path = Path(golden_dataset_path)
        self.max_workers = max_workers
        self._golden_dataset: Optional[List[Dict[str, Any]]] = None
        self._judges: Optional[Dict[str, Any]] = None

    def load_golden_dataset(self) -> List[Dict[str, Any]]:
        """
        Load golden dataset from JSON file.

        Returns:
            List of test cases.
        """
        if self._golden_dataset is not None:
            return self._golden_dataset

        if not self.golden_dataset_path.exists():
            logger.warning(f"Golden dataset not found at {self.golden_dataset_path}")
            # Return empty dataset
            return []

        try:
            with open(self.golden_dataset_path, 'r') as f:
                self._golden_dataset = json.load(f)
                logger.info(
                    f"Loaded {len(self._golden_dataset)} test cases from "
                    f"{self.golden_dataset_path}"
                )
                return self._golden_dataset
        except Exception as e:
            logger.error(f"Failed to load golden dataset: {e}")
            raise

    def get_judges(self) -> Dict[str, Any]:
        """
        Load all compliance judges.

        Returns:
            Dictionary mapping framework to list of judges.
        """
        if self._judges is not None:
            return self._judges

        from backend.judges import (
            # GDPR Judges
            GDPRArticle22Judge,
            GDPRArticle17Judge,
            GDPRArticle32Judge,
            # SOX Judges
            SOXSection404Judge,
            SOXSection302Judge,
            SOXAuditTrailJudge,
            # EU AI Act Judges
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

        logger.info("Loaded all 9 compliance judges for evaluation")
        return self._judges

    def run_judge_on_testcases(
        self,
        judge,
        test_cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Run a single judge on test cases.

        Args:
            judge: The compliance judge to evaluate.
            test_cases: List of test cases for this judge.

        Returns:
            List of evaluation results.
        """
        results = []

        for test_case in test_cases:
            description = test_case.get('description', '')

            try:
                # Run judge evaluation
                # Note: In real evaluation, we'd pass retrieved chunks
                # For now, we'll pass empty list to test judge logic
                result = judge.evaluate(
                    submission=description,
                    retrieved_chunks=[]
                )

                # Format result
                eval_result = {
                    'test_id': test_case.get('test_id'),
                    'violation_detected': result is not None and result.get('violation_detected', False),
                    'severity': result.get('severity') if result else 'NONE',
                    'confidence': result.get('confidence', 0.0) if result else 0.0,
                    'article_violated': result.get('article_violated') if result else None
                }

                results.append(eval_result)

                logger.debug(
                    f"{judge.judge_id} on {test_case.get('test_id')}: "
                    f"{'VIOLATION' if eval_result['violation_detected'] else 'PASS'}"
                )

            except Exception as e:
                logger.error(
                    f"Judge {judge.judge_id} failed on test {test_case.get('test_id')}: {e}"
                )
                # Record as failure
                results.append({
                    'test_id': test_case.get('test_id'),
                    'violation_detected': False,
                    'severity': 'NONE',
                    'confidence': 0.0,
                    'error': str(e)
                })

        return results

    def evaluate_all_judges(
        self,
        use_parallel: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate all judges against golden dataset.

        Args:
            use_parallel: If True, run judges in parallel.

        Returns:
            Dictionary with evaluation results and metrics.
        """
        # Load golden dataset
        golden_dataset = self.load_golden_dataset()

        if not golden_dataset:
            logger.warning("Golden dataset is empty, cannot evaluate")
            return {
                "status": "error",
                "message": "Golden dataset is empty or not found",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Load judges
        judges = self.get_judges()

        # Group test cases by judge
        judge_testcases: Dict[str, List[Dict[str, Any]]] = {}
        for test_case in golden_dataset:
            judge_id = test_case.get('judge_id')
            if judge_id not in judge_testcases:
                judge_testcases[judge_id] = []
            judge_testcases[judge_id].append(test_case)

        logger.info(
            f"Evaluating {len(judge_testcases)} judges with "
            f"{len(golden_dataset)} total test cases"
        )

        # Run evaluations
        all_metrics: List[EvaluationMetrics] = []
        judge_results = {}

        if use_parallel:
            # Parallel execution
            futures = {}
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all judge evaluations
                for framework, framework_judges in judges.items():
                    for judge in framework_judges:
                        test_cases = judge_testcases.get(judge.judge_id, [])
                        if not test_cases:
                            logger.warning(f"No test cases for {judge.judge_id}")
                            continue

                        future = executor.submit(
                            self.run_judge_on_testcases,
                            judge,
                            test_cases
                        )
                        futures[future] = (judge, test_cases)

                # Collect results
                for future in as_completed(futures):
                    judge, test_cases = futures[future]
                    try:
                        results = future.result()

                        # Calculate metrics
                        metrics = evaluate_judge_performance(
                            judge_results=results,
                            golden_dataset=test_cases,
                            judge_id=judge.judge_id
                        )

                        all_metrics.append(metrics)
                        judge_results[judge.judge_id] = metrics.to_dict()

                    except Exception as e:
                        logger.error(f"Failed to evaluate {judge.judge_id}: {e}")

        else:
            # Sequential execution
            for framework, framework_judges in judges.items():
                for judge in framework_judges:
                    test_cases = judge_testcases.get(judge.judge_id, [])
                    if not test_cases:
                        continue

                    results = self.run_judge_on_testcases(judge, test_cases)

                    metrics = evaluate_judge_performance(
                        judge_results=results,
                        golden_dataset=test_cases,
                        judge_id=judge.judge_id
                    )

                    all_metrics.append(metrics)
                    judge_results[judge.judge_id] = metrics.to_dict()

        # Aggregate metrics
        aggregate = aggregate_metrics(all_metrics)

        # Build final report
        report = {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "dataset_info": {
                "total_test_cases": len(golden_dataset),
                "judges_evaluated": len(all_metrics),
                "dataset_path": str(self.golden_dataset_path)
            },
            "aggregate_metrics": aggregate,
            "judge_metrics": judge_results,
            "targets": {
                "tpr_target": 0.90,
                "tnr_target": 0.90,
                "critical_recall_target": 0.95
            },
            "summary": {
                "all_targets_met": aggregate.get("targets_met", False),
                "judges_meeting_targets": aggregate.get("judges_meeting_targets", 0),
                "total_judges": aggregate.get("total_judges", 0)
            }
        }

        logger.info(
            f"Evaluation complete: {report['summary']['judges_meeting_targets']}"
            f"/{report['summary']['total_judges']} judges meeting targets"
        )

        return report

    def evaluate_single_judge(
        self,
        judge_id: str
    ) -> Dict[str, Any]:
        """
        Evaluate a single judge.

        Args:
            judge_id: Judge identifier to evaluate.

        Returns:
            Evaluation results for the judge.
        """
        golden_dataset = self.load_golden_dataset()
        judges = self.get_judges()

        # Find test cases for this judge
        test_cases = [
            case for case in golden_dataset
            if case.get('judge_id') == judge_id
        ]

        if not test_cases:
            return {
                "status": "error",
                "message": f"No test cases found for judge {judge_id}"
            }

        # Find the judge
        target_judge = None
        for framework_judges in judges.values():
            for judge in framework_judges:
                if judge.judge_id == judge_id:
                    target_judge = judge
                    break
            if target_judge:
                break

        if not target_judge:
            return {
                "status": "error",
                "message": f"Judge {judge_id} not found"
            }

        # Run evaluation
        results = self.run_judge_on_testcases(target_judge, test_cases)

        # Calculate metrics
        metrics = evaluate_judge_performance(
            judge_results=results,
            golden_dataset=test_cases,
            judge_id=judge_id
        )

        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "judge_id": judge_id,
            "test_cases_evaluated": len(test_cases),
            "metrics": metrics.to_dict()
        }


# Singleton instance
_runner_instance: Optional[EvaluationRunner] = None


def get_evaluation_runner() -> EvaluationRunner:
    """
    Get global EvaluationRunner singleton.

    Returns:
        EvaluationRunner instance.
    """
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = EvaluationRunner()
    return _runner_instance
