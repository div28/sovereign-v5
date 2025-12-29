#!/usr/bin/env python3
"""
Agentic Evaluation Suite for Sovereign V5

Tests the multi-agent compliance system against the golden dataset.
Handles async job polling and compares results to expected values.

Usage:
    python run_agentic_evals.py                    # Run all scenarios
    python run_agentic_evals.py --limit 5          # Run first 5 only
    python run_agentic_evals.py --framework gdpr   # Filter by framework
"""

import os
import sys
import csv
import json
import time
import argparse
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

# Configuration
API_BASE = "https://sovereign-v5.onrender.com"
POLL_INTERVAL = 3  # seconds
POLL_TIMEOUT = 180  # seconds (increased for Render cold starts)
REQUEST_DELAY = 2  # seconds between requests (rate limiting)

GOLDEN_DATASET_PATH = os.path.join(os.path.dirname(__file__), "golden_dataset.csv")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "agentic_eval_results.csv")


@dataclass
class EvalResult:
    """Single evaluation result."""
    scenario_id: str
    description: str
    framework: str
    expected_verdict: str
    expected_severity: str
    actual_verdict: str
    actual_severity: str
    confidence: float
    iterations: int
    risk_score: int
    chunks_retrieved: int
    latency_ms: float
    match: bool
    severity_match: bool
    error_type: str
    error_message: str
    violations_count: int
    job_id: str


def load_golden_dataset(path: str, limit: Optional[int] = None, framework_filter: Optional[str] = None) -> List[Dict]:
    """Load golden dataset from CSV."""
    scenarios = []

    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter by framework if specified
            if framework_filter:
                row_framework = row.get('framework', '').lower()
                if framework_filter.lower() not in row_framework:
                    continue

            scenarios.append({
                'test_id': row.get('test_id', ''),
                'framework': row.get('framework', ''),
                'scenario_type': row.get('scenario_type', ''),
                'policy_summary': row.get('policy_summary', ''),
                'ai_system_description': row.get('ai_system_description', ''),
                'expected_verdict': row.get('expected_verdict', ''),
                'expected_severity': row.get('expected_severity', 'NONE'),
                'difficulty': row.get('difficulty', ''),
                'notes': row.get('notes', '')
            })

            if limit and len(scenarios) >= limit:
                break

    return scenarios


def map_framework_to_api(framework: str) -> List[str]:
    """Map golden dataset framework names to API framework codes."""
    framework_lower = framework.lower()
    if 'gdpr' in framework_lower:
        return ['gdpr']
    elif 'sox' in framework_lower:
        return ['sox']
    elif 'eu ai' in framework_lower or 'euai' in framework_lower:
        return ['euai']
    else:
        # Default to all frameworks for unknown
        return ['gdpr', 'sox', 'euai']


def submit_analysis(description: str, frameworks: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Submit analysis request and return job_id.

    Returns:
        Tuple of (job_id, error_message)
    """
    try:
        response = requests.post(
            f"{API_BASE}/api/analyze/agentic",
            json={
                "description": description,
                "frameworks": frameworks,
                "include_agent_trace": True
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            return data.get('job_id'), None
        else:
            return None, f"HTTP {response.status_code}: {response.text[:200]}"

    except requests.exceptions.Timeout:
        return None, "Request timeout"
    except requests.exceptions.RequestException as e:
        return None, f"Request failed: {str(e)}"


def poll_job(job_id: str, timeout: int = POLL_TIMEOUT) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Poll job until complete or timeout.

    Returns:
        Tuple of (result_dict, error_message)
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"{API_BASE}/api/jobs/{job_id}",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get('status', '')

                if status == 'complete':
                    return data.get('result', {}), None
                elif status == 'error':
                    return None, data.get('error', 'Unknown error')
                elif status in ['pending', 'processing']:
                    time.sleep(POLL_INTERVAL)
                    continue
                else:
                    return None, f"Unknown status: {status}"

            elif response.status_code == 404:
                return None, f"Job {job_id} not found"
            else:
                time.sleep(POLL_INTERVAL)

        except requests.exceptions.RequestException as e:
            time.sleep(POLL_INTERVAL)

    return None, f"Timeout after {timeout}s"


def evaluate_scenario(scenario: Dict) -> EvalResult:
    """
    Run a single scenario through the agentic API.

    Returns:
        EvalResult with comparison to expected values
    """
    start_time = time.time()

    test_id = scenario['test_id']
    description = scenario['ai_system_description']
    framework = scenario['framework']
    expected_verdict = scenario['expected_verdict'].upper()
    expected_severity = scenario['expected_severity'].upper()

    print(f"\n  [{test_id}] Submitting...", end=" ", flush=True)

    # Submit analysis
    frameworks = map_framework_to_api(framework)
    job_id, error = submit_analysis(description, frameworks)

    if error:
        print(f"SUBMIT ERROR: {error}")
        return EvalResult(
            scenario_id=test_id,
            description=description[:100],
            framework=framework,
            expected_verdict=expected_verdict,
            expected_severity=expected_severity,
            actual_verdict="ERROR",
            actual_severity="NONE",
            confidence=0.0,
            iterations=0,
            risk_score=0,
            chunks_retrieved=0,
            latency_ms=(time.time() - start_time) * 1000,
            match=False,
            severity_match=False,
            error_type="SUBMIT_ERROR",
            error_message=error,
            violations_count=0,
            job_id=""
        )

    print(f"job_id={job_id[:8]}... polling...", end=" ", flush=True)

    # Poll for results
    result, error = poll_job(job_id)
    latency_ms = (time.time() - start_time) * 1000

    if error:
        print(f"POLL ERROR: {error}")
        return EvalResult(
            scenario_id=test_id,
            description=description[:100],
            framework=framework,
            expected_verdict=expected_verdict,
            expected_severity=expected_severity,
            actual_verdict="ERROR",
            actual_severity="NONE",
            confidence=0.0,
            iterations=0,
            risk_score=0,
            chunks_retrieved=0,
            latency_ms=latency_ms,
            match=False,
            severity_match=False,
            error_type="POLL_ERROR",
            error_message=error,
            violations_count=0,
            job_id=job_id or ""
        )

    # Extract results
    violations = result.get('violations', [])
    violations_count = len(violations)
    risk_score = result.get('risk_score', 0)
    confidence = result.get('confidence', 0.0)
    iterations = result.get('iterations', 1)
    chunks_retrieved = result.get('chunks_retrieved', 0)

    # Determine actual verdict
    if violations_count > 0:
        actual_verdict = "VIOLATION"
        # Get highest severity from violations
        severities = [v.get('severity', 'NONE').upper() for v in violations]
        severity_order = ['CRITICAL', 'MAJOR', 'MINOR', 'NONE']
        actual_severity = min(severities, key=lambda s: severity_order.index(s) if s in severity_order else 99)
    else:
        actual_verdict = "COMPLIANT"
        actual_severity = "NONE"

    # Compare to expected
    verdict_match = (actual_verdict == expected_verdict)
    severity_match = (actual_severity == expected_severity) if verdict_match else False

    # Determine error type for mismatches
    error_type = ""
    if not verdict_match:
        if expected_verdict == "VIOLATION" and actual_verdict == "COMPLIANT":
            error_type = "FALSE_NEGATIVE"
        elif expected_verdict == "COMPLIANT" and actual_verdict == "VIOLATION":
            error_type = "FALSE_POSITIVE"
    elif not severity_match:
        error_type = "SEVERITY_MISMATCH"

    status = "PASS" if verdict_match else "FAIL"
    print(f"{status} (actual={actual_verdict}, expected={expected_verdict}, {latency_ms:.0f}ms)")

    return EvalResult(
        scenario_id=test_id,
        description=description[:100],
        framework=framework,
        expected_verdict=expected_verdict,
        expected_severity=expected_severity,
        actual_verdict=actual_verdict,
        actual_severity=actual_severity,
        confidence=confidence,
        iterations=iterations,
        risk_score=risk_score,
        chunks_retrieved=chunks_retrieved,
        latency_ms=latency_ms,
        match=verdict_match,
        severity_match=severity_match,
        error_type=error_type,
        error_message="",
        violations_count=violations_count,
        job_id=job_id
    )


def calculate_metrics(results: List[EvalResult]) -> Dict[str, Any]:
    """Calculate accuracy metrics from results."""
    total = len(results)
    if total == 0:
        return {}

    # Overall accuracy
    correct = sum(1 for r in results if r.match)
    accuracy = correct / total

    # Confusion matrix
    tp = sum(1 for r in results if r.expected_verdict == "VIOLATION" and r.actual_verdict == "VIOLATION")
    tn = sum(1 for r in results if r.expected_verdict == "COMPLIANT" and r.actual_verdict == "COMPLIANT")
    fp = sum(1 for r in results if r.expected_verdict == "COMPLIANT" and r.actual_verdict == "VIOLATION")
    fn = sum(1 for r in results if r.expected_verdict == "VIOLATION" and r.actual_verdict == "COMPLIANT")

    # Precision, Recall, F1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # Per-framework accuracy
    framework_results = defaultdict(lambda: {'correct': 0, 'total': 0})
    for r in results:
        fw = r.framework.upper()
        framework_results[fw]['total'] += 1
        if r.match:
            framework_results[fw]['correct'] += 1

    framework_accuracy = {
        fw: data['correct'] / data['total'] if data['total'] > 0 else 0
        for fw, data in framework_results.items()
    }

    # Error breakdown
    errors = defaultdict(int)
    for r in results:
        if r.error_type:
            errors[r.error_type] += 1

    # Average metrics
    avg_confidence = sum(r.confidence for r in results) / total
    avg_latency = sum(r.latency_ms for r in results) / total
    avg_iterations = sum(r.iterations for r in results) / total

    return {
        'total': total,
        'correct': correct,
        'accuracy': accuracy,
        'confusion_matrix': {
            'TP': tp,
            'TN': tn,
            'FP': fp,
            'FN': fn
        },
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'framework_accuracy': framework_accuracy,
        'error_breakdown': dict(errors),
        'avg_confidence': avg_confidence,
        'avg_latency_ms': avg_latency,
        'avg_iterations': avg_iterations
    }


def save_results(results: List[EvalResult], output_path: str):
    """Save results to CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if results:
            fieldnames = list(asdict(results[0]).keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(asdict(r))

    print(f"\nResults saved to: {output_path}")


def print_summary(metrics: Dict[str, Any]):
    """Print summary metrics."""
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)

    print(f"\nOverall Accuracy: {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']})")

    print(f"\nConfusion Matrix:")
    cm = metrics['confusion_matrix']
    print(f"  True Positives:  {cm['TP']:3d}  (correctly detected violations)")
    print(f"  True Negatives:  {cm['TN']:3d}  (correctly passed compliant)")
    print(f"  False Positives: {cm['FP']:3d}  (false alarms)")
    print(f"  False Negatives: {cm['FN']:3d}  (missed violations)")

    print(f"\nPrecision: {metrics['precision']:.1%}")
    print(f"Recall:    {metrics['recall']:.1%}")
    print(f"F1 Score:  {metrics['f1']:.1%}")

    print(f"\nPer-Framework Accuracy:")
    for fw, acc in sorted(metrics['framework_accuracy'].items()):
        print(f"  {fw:15s}: {acc:.1%}")

    if metrics['error_breakdown']:
        print(f"\nError Breakdown:")
        for error_type, count in sorted(metrics['error_breakdown'].items()):
            print(f"  {error_type:20s}: {count}")

    print(f"\nPerformance:")
    print(f"  Avg Confidence:  {metrics['avg_confidence']:.2f}")
    print(f"  Avg Latency:     {metrics['avg_latency_ms']:.0f}ms")
    print(f"  Avg Iterations:  {metrics['avg_iterations']:.1f}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Run agentic evals against golden dataset")
    parser.add_argument('--limit', type=int, help="Limit number of scenarios to run")
    parser.add_argument('--framework', type=str, help="Filter by framework (gdpr, sox, euai)")
    parser.add_argument('--output', type=str, default=OUTPUT_PATH, help="Output CSV path")
    parser.add_argument('--dataset', type=str, default=GOLDEN_DATASET_PATH, help="Golden dataset path")
    args = parser.parse_args()

    print("=" * 60)
    print("SOVEREIGN V5 - AGENTIC EVALUATION SUITE")
    print("=" * 60)
    print(f"API: {API_BASE}")
    print(f"Dataset: {args.dataset}")
    print(f"Limit: {args.limit or 'all'}")
    print(f"Framework filter: {args.framework or 'none'}")
    print(f"Output: {args.output}")

    # Load scenarios
    scenarios = load_golden_dataset(args.dataset, args.limit, args.framework)
    print(f"\nLoaded {len(scenarios)} scenarios")

    if not scenarios:
        print("No scenarios to run!")
        return

    # Run evaluations
    print("\nRunning evaluations...")
    results = []

    for i, scenario in enumerate(scenarios):
        print(f"\n[{i+1}/{len(scenarios)}]", end="")
        result = evaluate_scenario(scenario)
        results.append(result)

        # Rate limiting delay
        if i < len(scenarios) - 1:
            time.sleep(REQUEST_DELAY)

    # Calculate metrics
    metrics = calculate_metrics(results)

    # Save results
    save_results(results, args.output)

    # Print summary
    print_summary(metrics)

    # Save metrics as JSON
    metrics_path = args.output.replace('.csv', '_metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {metrics_path}")

    # Return exit code based on accuracy threshold
    if metrics['accuracy'] >= 0.8:
        print("\n[PASS] Accuracy >= 80%")
        sys.exit(0)
    else:
        print("\n[FAIL] Accuracy < 80%")
        sys.exit(1)


if __name__ == "__main__":
    main()
