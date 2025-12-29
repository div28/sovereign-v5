#!/usr/bin/env python3
"""
Reflection Loop Evaluation for Sovereign V5

Tests edge cases designed to trigger the Plan-Act-Reflect loop.
Verifies that low-confidence findings trigger additional iterations.

Usage:
    python eval_reflection_loop.py
"""

import os
import sys
import csv
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Configuration
API_BASE = "https://sovereign-v5.onrender.com"
POLL_INTERVAL = 3
POLL_TIMEOUT = 150  # Longer timeout for reflection scenarios
REQUEST_DELAY = 2

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "reflection_loop_results.csv")


# 10 Hard edge cases designed to trigger reflection loop
EDGE_CASES = [
    {
        "id": "EDGE_001",
        "name": "Ambiguous Human Review",
        "framework": "gdpr",
        "description": """Our AI hiring system scores candidates 1-100. Technically a human
        reviews each decision, but the review takes 30 seconds on average and the human
        agrees with the AI 99.7% of the time. Is the human review "meaningful" under
        GDPR Article 22? The system processes 500 candidates daily.""",
        "expected_iterations": 2,
        "notes": "Borderline meaningful human oversight"
    },
    {
        "id": "EDGE_002",
        "name": "Partial Data Deletion",
        "framework": "gdpr",
        "description": """When users request data deletion, we remove their profile but:
        - Anonymized analytics data is retained
        - Backup tapes keep data for 90 days
        - Third-party vendors are notified but we don't verify deletion
        - Some data is kept for "legal compliance" (unspecified)
        Is this compliant with Article 17 Right to Erasure?""",
        "expected_iterations": 2,
        "notes": "Multiple partial compliance factors"
    },
    {
        "id": "EDGE_003",
        "name": "Voluntary Emotion AI",
        "framework": "euai",
        "description": """Our workplace wellness app uses emotion AI to detect stress.
        - Employees opt-in voluntarily
        - Individual data never shared with employer
        - Only aggregate trends reported
        - Employee controls their own data
        Does the EU AI Act prohibition on workplace emotion AI apply to voluntary wellness tools?""",
        "expected_iterations": 2,
        "notes": "EU AI Act Article 5 exception ambiguity"
    },
    {
        "id": "EDGE_004",
        "name": "Compensating Controls",
        "framework": "sox",
        "description": """Our startup has 5 employees. Traditional segregation of duties
        is impossible - the CFO both creates and approves transactions. We implemented
        compensating controls: daily board review, external monthly audit, automated
        anomaly detection. Does this satisfy SOX Section 404?""",
        "expected_iterations": 2,
        "notes": "Small company SOX exception scenario"
    },
    {
        "id": "EDGE_005",
        "name": "AI Recommendation vs Decision",
        "framework": "gdpr",
        "description": """Our loan system works as follows:
        - AI generates a risk score and recommendation (approve/deny)
        - Loan officers see the recommendation
        - Officers can override but rarely do (5% override rate)
        - Officers spend 2 minutes average reviewing each case
        - No automated denials - all technically "reviewed"
        Is this automated decision-making with legal effects?""",
        "expected_iterations": 2,
        "notes": "WP29 guidelines on meaningful human intervention"
    },
    {
        "id": "EDGE_006",
        "name": "Biometric Research Exception",
        "framework": "euai",
        "description": """University research project uses facial recognition:
        - All participants signed informed consent
        - Data used only for academic research on bias detection
        - Not deployed in any real-world application
        - Results published to improve AI fairness
        Does the EU AI Act prohibition apply to research contexts?""",
        "expected_iterations": 2,
        "notes": "Research vs production deployment"
    },
    {
        "id": "EDGE_007",
        "name": "AI-Generated Audit Trail",
        "framework": "sox",
        "description": """Our financial AI system:
        - Logs every transaction with timestamp
        - AI explains its decisions in natural language
        - Logs stored in immutable blockchain
        - But: AI reasoning may be post-hoc rationalization
        - Original model weights not preserved
        Do AI-generated explanations satisfy SOX audit trail requirements?""",
        "expected_iterations": 2,
        "notes": "Novel audit trail for AI systems"
    },
    {
        "id": "EDGE_008",
        "name": "Encryption with Gaps",
        "framework": "gdpr",
        "description": """Our security posture:
        - Data encrypted at rest (AES-256)
        - Data encrypted in transit (TLS 1.3)
        - But: data is decrypted for processing
        - Processing happens on shared infrastructure
        - Encryption keys rotated annually
        - No hardware security modules
        Does this satisfy Article 32 appropriate security?""",
        "expected_iterations": 2,
        "notes": "Partial security implementation"
    },
    {
        "id": "EDGE_009",
        "name": "Hybrid AI System",
        "framework": "euai",
        "description": """Our customer service system:
        - AI chatbot handles initial queries
        - Escalates to humans for complex issues
        - AI suggests responses for human agents
        - Human can modify or reject suggestions
        - Some responses are templated (AI selects template)
        Is this a high-risk AI system requiring conformity assessment?""",
        "expected_iterations": 2,
        "notes": "Mixed AI/human decision-making"
    },
    {
        "id": "EDGE_010",
        "name": "Cross-Framework Conflict",
        "framework": "gdpr",
        "description": """Financial services company situation:
        - GDPR requires data minimization and deletion
        - SOX requires 7-year retention of financial records
        - User requests deletion of their loan application data
        - Loan was denied (still financial record)
        - User claims right to erasure
        How do we resolve conflicting regulatory requirements?""",
        "expected_iterations": 2,
        "notes": "GDPR vs SOX conflict"
    }
]


@dataclass
class ReflectionResult:
    """Single reflection loop test result."""
    scenario_id: str
    scenario_name: str
    framework: str
    iterations: int
    expected_iterations: int
    triggered_reflection: bool
    initial_confidence: float
    final_confidence: float
    confidence_improved: bool
    low_confidence_flags: int
    violations_count: int
    risk_score: int
    latency_ms: float
    error: str


def submit_and_wait(description: str, frameworks: List[str]) -> Dict[str, Any]:
    """Submit analysis and wait for completion."""
    try:
        # Submit
        response = requests.post(
            f"{API_BASE}/api/analyze/agentic",
            json={
                "description": description,
                "frameworks": frameworks,
                "include_agent_trace": True
            },
            timeout=30
        )

        if response.status_code != 200:
            return {"error": f"Submit failed: {response.status_code}"}

        job_id = response.json().get('job_id')
        if not job_id:
            return {"error": "No job_id returned"}

        # Poll
        start_time = time.time()
        while time.time() - start_time < POLL_TIMEOUT:
            poll_response = requests.get(
                f"{API_BASE}/api/jobs/{job_id}",
                timeout=10
            )

            if poll_response.status_code == 200:
                data = poll_response.json()
                status = data.get('status', '')

                if status == 'complete':
                    result = data.get('result', {})
                    result['_latency_ms'] = (time.time() - start_time) * 1000
                    return result
                elif status == 'error':
                    return {"error": data.get('error', 'Unknown error')}

            time.sleep(POLL_INTERVAL)

        return {"error": f"Timeout after {POLL_TIMEOUT}s"}

    except Exception as e:
        return {"error": str(e)}


def evaluate_edge_case(case: Dict) -> ReflectionResult:
    """Evaluate a single edge case for reflection loop behavior."""
    print(f"\n  [{case['id']}] {case['name']}...", end=" ", flush=True)

    start_time = time.time()
    result = submit_and_wait(case['description'], [case['framework']])
    latency_ms = result.get('_latency_ms', (time.time() - start_time) * 1000)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        return ReflectionResult(
            scenario_id=case['id'],
            scenario_name=case['name'],
            framework=case['framework'],
            iterations=0,
            expected_iterations=case['expected_iterations'],
            triggered_reflection=False,
            initial_confidence=0,
            final_confidence=0,
            confidence_improved=False,
            low_confidence_flags=0,
            violations_count=0,
            risk_score=0,
            latency_ms=latency_ms,
            error=result['error']
        )

    # Extract metrics
    iterations = result.get('iterations', 1)
    confidence = result.get('confidence', 0)
    violations = result.get('violations', [])
    risk_score = result.get('risk_score', 0)

    # Get agent trace data
    agent_trace = result.get('agent_trace', {})
    low_conf_flags = len(agent_trace.get('low_confidence_flags', []))

    # Check confidence improvements
    conf_improvements = result.get('confidence_improvements', {})
    initial_conf = conf_improvements.get('initial', confidence)
    final_conf = conf_improvements.get('final', confidence)

    triggered = iterations > 1
    improved = final_conf > initial_conf

    status = "REFLECTED" if triggered else "NO REFLECTION"
    print(f"{status} (iter={iterations}, conf={confidence:.2f})")

    return ReflectionResult(
        scenario_id=case['id'],
        scenario_name=case['name'],
        framework=case['framework'],
        iterations=iterations,
        expected_iterations=case['expected_iterations'],
        triggered_reflection=triggered,
        initial_confidence=initial_conf,
        final_confidence=final_conf,
        confidence_improved=improved,
        low_confidence_flags=low_conf_flags,
        violations_count=len(violations),
        risk_score=risk_score,
        latency_ms=latency_ms,
        error=""
    )


def save_results(results: List[ReflectionResult], output_path: str):
    """Save results to CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if results:
            fieldnames = list(asdict(results[0]).keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(asdict(r))

    print(f"\nResults saved to: {output_path}")


def print_summary(results: List[ReflectionResult]):
    """Print summary of reflection loop testing."""
    print("\n" + "=" * 60)
    print("REFLECTION LOOP EVALUATION SUMMARY")
    print("=" * 60)

    valid = [r for r in results if not r.error]
    if not valid:
        print("No valid results!")
        return

    # Reflection rate
    reflected = sum(1 for r in valid if r.triggered_reflection)
    print(f"\nScenarios Tested: {len(valid)}")
    print(f"Reflection Triggered: {reflected}/{len(valid)} ({reflected/len(valid)*100:.0f}%)")

    # Average iterations
    avg_iterations = sum(r.iterations for r in valid) / len(valid)
    max_iterations = max(r.iterations for r in valid)
    print(f"\nIterations:")
    print(f"  Average: {avg_iterations:.1f}")
    print(f"  Maximum: {max_iterations}")

    # Confidence improvement
    improved = sum(1 for r in valid if r.confidence_improved)
    print(f"\nConfidence Improved: {improved}/{len(valid)}")

    # Average confidence
    avg_initial = sum(r.initial_confidence for r in valid) / len(valid)
    avg_final = sum(r.final_confidence for r in valid) / len(valid)
    print(f"\nAverage Confidence:")
    print(f"  Initial: {avg_initial:.2f}")
    print(f"  Final:   {avg_final:.2f}")

    # Low confidence flags
    total_flags = sum(r.low_confidence_flags for r in valid)
    print(f"\nTotal Low-Confidence Flags: {total_flags}")

    # Per-scenario breakdown
    print(f"\nPer-Scenario Results:")
    for r in results:
        status = "ERROR" if r.error else ("REFLECTED" if r.triggered_reflection else "SINGLE")
        print(f"  {r.scenario_id}: {status} (iter={r.iterations}, conf={r.final_confidence:.2f})")

    print("=" * 60)


def main():
    print("=" * 60)
    print("REFLECTION LOOP EVALUATION")
    print("=" * 60)
    print(f"Testing {len(EDGE_CASES)} edge cases designed to trigger reflection")

    results = []

    for i, case in enumerate(EDGE_CASES):
        print(f"\n[{i+1}/{len(EDGE_CASES)}]", end="")
        result = evaluate_edge_case(case)
        results.append(result)

        # Rate limiting
        if i < len(EDGE_CASES) - 1:
            time.sleep(REQUEST_DELAY)

    # Save and summarize
    save_results(results, OUTPUT_PATH)
    print_summary(results)


if __name__ == "__main__":
    main()
