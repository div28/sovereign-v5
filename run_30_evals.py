#!/usr/bin/env python3
import requests
import pandas as pd
import time
import argparse
from pathlib import Path

def run_evals(api_url="https://sovereign-v5.onrender.com", num_scenarios=30):
    """Run evaluations and populate error_analysis_results.csv"""

    # Read golden dataset
    golden_csv = Path("evals/golden_dataset.csv")
    if not golden_csv.exists():
        print(f"Error: {golden_csv} not found")
        return

    df_golden = pd.read_csv(golden_csv)
    df_golden = df_golden.head(num_scenarios)

    results = []

    print("Starting evaluation run...\n")

    for idx, row in df_golden.iterrows():
        scenario_num = idx + 1
        test_id = row['test_id']
        framework = row['framework']
        policy = row['policy_summary']
        ai_desc = row['ai_system_description']
        expected_verdict = row['expected_verdict']
        expected_severity = row.get('expected_severity', 'NONE')
        scenario_type = row.get('scenario_type', 'unknown')

        print(f"Running scenario {scenario_num}/{num_scenarios}... {test_id}")

        try:
            # Call API
            response = requests.post(
                f"{api_url}/api/analyze-compliance",
                json={
                    "policy_text": policy,
                    "ai_system_description": ai_desc,
                    "frameworks": [framework]
                },
                timeout=30
            )

            if response.status_code != 200:
                print(f"  ✗ API error: {response.status_code}")
                continue

            data = response.json()
            violations = data.get("violations", [])

            # Extract actual results
            if violations:
                v = violations[0]
                actual_verdict = "VIOLATION" if v.get("violation_detected", False) else "COMPLIANT"
                actual_severity = v.get("severity", "NONE")
                confidence = v.get("confidence", 0)
                reasoning = v.get("reasoning", "")
            else:
                actual_verdict = "COMPLIANT"
                actual_severity = "NONE"
                confidence = 1.0
                reasoning = ""

            # Compare
            match = (expected_verdict == actual_verdict)
            severity_match = "N/A"
            if match and expected_verdict == "VIOLATION":
                severity_match = (expected_severity == actual_severity)

            reasoning_present = "YES" if reasoning else "NO"
            confidence_pct = f"{int(confidence * 100)}%"

            # Record result
            result = {
                "test_id": test_id,
                "framework": framework,
                "scenario_type": scenario_type,
                "expected_verdict": expected_verdict,
                "actual_verdict": actual_verdict,
                "match": match,
                "error_type": "",  # User fills this in
                "judge_confidence": confidence_pct,
                "judge_reasoning_present": reasoning_present,
                "severity_match": severity_match,
                "notes": ""  # User fills this in
            }

            results.append(result)
            print(f"  ✓ {actual_verdict} (confidence: {confidence_pct})")

        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            continue

        time.sleep(1)  # Be gentle on API

    # Write results
    df_results = pd.DataFrame(results)
    output_path = Path("evals/error_analysis_results.csv")
    df_results.to_csv(output_path, index=False)

    # Summary
    matches = df_results['match'].sum()
    total = len(df_results)
    match_pct = (matches / total * 100) if total > 0 else 0

    print(f"\n========== EVAL RESULTS ==========")
    print(f"Total Scenarios Run: {total}/{num_scenarios}")
    print(f"Matches: {matches} ({match_pct:.1f}%)")
    print(f"Mismatches: {total - matches} (for manual review)")
    print(f"\nGenerated: {output_path}")
    print(f"\nNext steps:")
    print(f"  1. Open evals/error_analysis_results.csv")
    print(f"  2. Review rows where match=FALSE")
    print(f"  3. Fill in error_type and notes columns")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="https://sovereign-v5.onrender.com")
    parser.add_argument("--scenarios", type=int, default=30)
    args = parser.parse_args()

    run_evals(args.api_url, args.scenarios)
