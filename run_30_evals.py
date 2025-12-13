#!/usr/bin/env python3
"""
Sovereign V5 Evaluation Runner

Automates running test scenarios from golden_dataset.csv through the
Sovereign V5 API and populates error_analysis_results.csv with results.

Usage:
    python run_30_evals.py
    python run_30_evals.py --api-url https://sovereign-v5.onrender.com --scenarios 30
    python run_30_evals.py --scenarios 10 --output evals/test_results.csv

Requirements:
    pip install requests pandas
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
    import pandas as pd
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install requests pandas")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_API_URL = "https://sovereign-v5.onrender.com"
DEFAULT_SCENARIOS = 30
DEFAULT_INPUT_CSV = "evals/golden_dataset.csv"
DEFAULT_OUTPUT_CSV = "evals/error_analysis_results.csv"

# Retry configuration
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 5

# API endpoint
API_ENDPOINT = "/api/analyze"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_framework(framework: str) -> str:
    """
    Normalize framework name for API compatibility.

    API expects: gdpr, sox, euai
    Golden dataset may have: GDPR, SOX, EU AI Act, etc.
    """
    framework_lower = framework.lower().strip()

    # Map variations to API-expected values
    mappings = {
        "gdpr": "gdpr",
        "sox": "sox",
        "eu ai act": "euai",
        "eu-ai": "euai",
        "euai": "euai",
        "eu ai": "euai",
    }

    return mappings.get(framework_lower, framework_lower)


def call_api(api_url: str, policy_text: str, ai_description: str, framework: str) -> dict:
    """
    Call the Sovereign V5 API to analyze compliance.

    Args:
        api_url: Base URL of the API
        policy_text: Policy summary text
        ai_description: AI system description
        framework: Regulatory framework to check

    Returns:
        API response as dict, or error dict if failed
    """
    endpoint = f"{api_url.rstrip('/')}{API_ENDPOINT}"

    # Normalize framework for API
    normalized_framework = normalize_framework(framework)

    # Build request payload
    # The API expects 'description' and 'frameworks' based on the FastAPI code
    payload = {
        "description": f"{policy_text}\n\n{ai_description}",
        "frameworks": [normalized_framework]
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=120  # 2 minute timeout for LLM processing
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.text[:500]
            }

    except requests.exceptions.Timeout:
        return {"error": True, "message": "Request timed out after 120 seconds"}
    except requests.exceptions.ConnectionError:
        return {"error": True, "message": "Connection error - is the API running?"}
    except Exception as e:
        return {"error": True, "message": str(e)}


def call_api_with_retry(api_url: str, policy_text: str, ai_description: str,
                        framework: str, test_id: str) -> dict:
    """
    Call API with retry logic.

    Args:
        api_url: Base URL of the API
        policy_text: Policy summary text
        ai_description: AI system description
        framework: Regulatory framework
        test_id: Test ID for logging

    Returns:
        API response dict
    """
    for attempt in range(MAX_RETRIES + 1):
        result = call_api(api_url, policy_text, ai_description, framework)

        if not result.get("error"):
            return result

        if attempt < MAX_RETRIES:
            print(f"    Retry {attempt + 1}/{MAX_RETRIES} for {test_id} in {RETRY_DELAY_SECONDS}s...")
            time.sleep(RETRY_DELAY_SECONDS)

    return result  # Return last error


def extract_verdict(api_response: dict) -> tuple:
    """
    Extract verdict information from API response.

    Args:
        api_response: Response from the API

    Returns:
        Tuple of (actual_verdict, severity, confidence, reasoning_present, article)
    """
    if api_response.get("error"):
        return ("ERROR", "N/A", "N/A", "NO", "N/A")

    violations = api_response.get("violations", [])

    if not violations:
        # No violations = COMPLIANT
        return ("COMPLIANT", "NONE", "N/A", "NO", "N/A")

    # Get first violation
    v = violations[0]

    actual_verdict = "VIOLATION" if v.get("violation_detected", True) else "COMPLIANT"
    severity = v.get("severity", "UNKNOWN")

    # Format confidence as percentage
    confidence = v.get("confidence")
    if confidence is not None:
        confidence_str = f"{int(confidence * 100)}%"
    else:
        confidence_str = "N/A"

    # Check if reasoning is present
    reasoning = v.get("reasoning", "")
    reasoning_present = "YES" if reasoning and len(str(reasoning)) > 10 else "NO"

    article = v.get("article_violated", "N/A")

    return (actual_verdict, severity, confidence_str, reasoning_present, article)


def compare_results(expected_verdict: str, actual_verdict: str,
                    expected_severity: str, actual_severity: str) -> tuple:
    """
    Compare expected vs actual results.

    Args:
        expected_verdict: Expected verdict from golden dataset
        actual_verdict: Actual verdict from API
        expected_severity: Expected severity level
        actual_severity: Actual severity level

    Returns:
        Tuple of (match, severity_match)
    """
    # Normalize verdicts for comparison
    expected_norm = expected_verdict.upper().strip()
    actual_norm = actual_verdict.upper().strip()

    # Handle various verdict formats
    if expected_norm in ["VIOLATION", "VIOLATED", "TRUE"]:
        expected_norm = "VIOLATION"
    elif expected_norm in ["COMPLIANT", "NONE", "FALSE", "NO_VIOLATION"]:
        expected_norm = "COMPLIANT"

    # Check verdict match
    match = expected_norm == actual_norm

    # Check severity match (only if verdict matches and is a violation)
    if match and actual_norm == "VIOLATION":
        expected_sev = expected_severity.upper().strip() if expected_severity else ""
        actual_sev = actual_severity.upper().strip() if actual_severity else ""
        severity_match = expected_sev == actual_sev
    elif match:
        severity_match = True  # Compliant cases don't have severity
    else:
        severity_match = "N/A"

    return (match, severity_match)


def load_golden_dataset(input_csv: str, num_scenarios: int) -> list:
    """
    Load scenarios from golden dataset CSV.

    Args:
        input_csv: Path to golden_dataset.csv
        num_scenarios: Number of scenarios to load

    Returns:
        List of scenario dicts
    """
    if not os.path.exists(input_csv):
        print(f"ERROR: Golden dataset not found at {input_csv}")
        sys.exit(1)

    scenarios = []

    try:
        df = pd.read_csv(input_csv)

        # Take first N scenarios
        df = df.head(num_scenarios)

        for _, row in df.iterrows():
            scenario = {
                "test_id": row.get("test_id", "UNKNOWN"),
                "framework": row.get("framework", "GDPR"),
                "scenario_type": row.get("scenario_type", "violation"),
                "policy_summary": row.get("policy_summary", ""),
                "ai_system_description": row.get("ai_system_description", ""),
                "expected_verdict": row.get("expected_verdict", "VIOLATION"),
                "expected_severity": row.get("expected_severity", "CRITICAL"),
                "difficulty": row.get("difficulty", "medium"),
                "notes": row.get("notes", "")
            }
            scenarios.append(scenario)

    except Exception as e:
        print(f"ERROR reading golden dataset: {e}")
        sys.exit(1)

    return scenarios


def save_results(results: list, output_csv: str, append: bool = True):
    """
    Save results to error_analysis_results.csv

    Args:
        results: List of result dicts
        output_csv: Output CSV path
        append: If True, append to existing file
    """
    # Define columns in order
    columns = [
        "test_id", "framework", "scenario_type", "expected_verdict",
        "actual_verdict", "match", "error_type", "judge_confidence",
        "judge_reasoning_present", "severity_match", "abstain", "notes",
        "timestamp", "article_detected"
    ]

    # Create output directory if needed
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if file exists and has content
    file_exists = output_path.exists() and output_path.stat().st_size > 0

    # Determine write mode
    mode = "a" if append and file_exists else "w"
    write_header = not (append and file_exists)

    try:
        with open(output_csv, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')

            if write_header:
                writer.writeheader()

            for result in results:
                writer.writerow(result)

        print(f"\nResults saved to: {output_csv}")

    except Exception as e:
        print(f"ERROR saving results: {e}")
        # Try to save to backup file
        backup_path = f"evals/error_analysis_backup_{int(time.time())}.csv"
        try:
            with open(backup_path, "w", newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(results)
            print(f"Backup saved to: {backup_path}")
        except:
            pass


def print_summary(results: list, total_scenarios: int):
    """
    Print evaluation summary.

    Args:
        results: List of result dicts
        total_scenarios: Total scenarios attempted
    """
    matches = sum(1 for r in results if r.get("match") == "TRUE")
    mismatches = sum(1 for r in results if r.get("match") == "FALSE")
    errors = sum(1 for r in results if r.get("actual_verdict") == "ERROR")

    match_pct = (matches / len(results) * 100) if results else 0

    print("\n" + "=" * 50)
    print("           EVAL RESULTS SUMMARY")
    print("=" * 50)
    print(f"Total Scenarios Run: {len(results)}/{total_scenarios}")
    print(f"Matches:    {matches} ({match_pct:.1f}%)")
    print(f"Mismatches: {mismatches} (for manual review)")
    print(f"Errors:     {errors}")
    print("=" * 50)
    print("\nGenerated: evals/error_analysis_results.csv")
    print("\nNext steps:")
    print("  1. Open the CSV and review mismatches")
    print("  2. Fill in 'error_type' column:")
    print("     - NONE: Correct answer")
    print("     - FALSE_NEGATIVE: Missed a violation")
    print("     - FALSE_POSITIVE: Flagged compliant as violation")
    print("     - SEVERITY_WRONG: Wrong severity level")
    print("  3. Add notes explaining patterns")
    print("=" * 50)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main entry point."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Run Sovereign V5 evaluation scenarios"
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"API base URL (default: {DEFAULT_API_URL})"
    )
    parser.add_argument(
        "--scenarios",
        type=int,
        default=DEFAULT_SCENARIOS,
        help=f"Number of scenarios to run (default: {DEFAULT_SCENARIOS})"
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_CSV,
        help=f"Input golden dataset CSV (default: {DEFAULT_INPUT_CSV})"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output results CSV (default: {DEFAULT_OUTPUT_CSV})"
    )
    parser.add_argument(
        "--no-append",
        action="store_true",
        help="Overwrite output file instead of appending"
    )

    args = parser.parse_args()

    # Print header
    print("=" * 50)
    print("    SOVEREIGN V5 EVALUATION RUNNER")
    print("=" * 50)
    print(f"API URL:    {args.api_url}")
    print(f"Scenarios:  {args.scenarios}")
    print(f"Input:      {args.input}")
    print(f"Output:     {args.output}")
    print(f"Append:     {not args.no_append}")
    print("=" * 50)
    print()

    # Load scenarios
    print(f"Loading scenarios from {args.input}...")
    scenarios = load_golden_dataset(args.input, args.scenarios)
    print(f"Loaded {len(scenarios)} scenarios\n")

    if not scenarios:
        print("No scenarios to run!")
        return

    # Run evaluations
    results = []
    start_time = time.time()

    for i, scenario in enumerate(scenarios, 1):
        test_id = scenario["test_id"]
        framework = scenario["framework"]

        # Progress indicator
        print(f"Running scenario {i}/{len(scenarios)}... {test_id} ({framework})")

        # Timestamp for this scenario
        timestamp = datetime.now().isoformat()

        # Call API
        api_response = call_api_with_retry(
            api_url=args.api_url,
            policy_text=scenario["policy_summary"],
            ai_description=scenario["ai_system_description"],
            framework=framework,
            test_id=test_id
        )

        # Extract verdict from response
        actual_verdict, severity, confidence, reasoning_present, article = extract_verdict(api_response)

        # Compare with expected
        match, severity_match = compare_results(
            scenario["expected_verdict"],
            actual_verdict,
            scenario["expected_severity"],
            severity
        )

        # Check for abstain
        abstain = "NO"
        if api_response.get("violations"):
            v = api_response["violations"][0]
            if v.get("abstain"):
                abstain = "YES"

        # Build result row
        result = {
            "test_id": test_id,
            "framework": framework,
            "scenario_type": scenario["scenario_type"],
            "expected_verdict": scenario["expected_verdict"],
            "actual_verdict": actual_verdict,
            "match": "TRUE" if match else "FALSE",
            "error_type": "",  # Leave blank for manual review
            "judge_confidence": confidence,
            "judge_reasoning_present": reasoning_present,
            "severity_match": "TRUE" if severity_match == True else ("FALSE" if severity_match == False else "N/A"),
            "abstain": abstain,
            "notes": "",  # Leave blank for manual review
            "timestamp": timestamp,
            "article_detected": article
        }

        results.append(result)

        # Status indicator
        status = "MATCH" if match else "MISMATCH"
        print(f"    -> {actual_verdict} (expected: {scenario['expected_verdict']}) [{status}]")

        # Small delay between API calls to avoid rate limiting
        if i < len(scenarios):
            time.sleep(1)

    # Calculate elapsed time
    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.1f} seconds")

    # Save results
    save_results(results, args.output, append=not args.no_append)

    # Print summary
    print_summary(results, args.scenarios)


if __name__ == "__main__":
    main()
