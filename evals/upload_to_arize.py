#!/usr/bin/env python3
"""
Upload Evaluation Results to Arize AI

Uploads agentic eval results to Arize for comparison with
parallel-judge baseline on the same dashboard.

Usage:
    python upload_to_arize.py
    python upload_to_arize.py --results agentic_eval_results.csv
"""

import os
import sys
import csv
import uuid
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configuration
ARIZE_SPACE_KEY = os.getenv("ARIZE_SPACE_KEY")
ARIZE_API_KEY = os.getenv("ARIZE_API_KEY")
MODEL_ID = "sovereign-multi-agent-v5"
MODEL_VERSION = "1.0.0"

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "agentic_eval_results.csv")


def load_results(path: str) -> List[Dict]:
    """Load evaluation results from CSV."""
    results = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)
    return results


def upload_to_arize(results: List[Dict], dry_run: bool = False):
    """
    Upload results to Arize AI.

    Schema:
    - prediction_id: unique ID
    - prediction_label: actual verdict (VIOLATION/COMPLIANT)
    - actual_label: expected verdict
    - model_id: "sovereign-multi-agent-v5"
    - Features: framework, confidence, iterations, risk_score, latency_ms, chunks_retrieved
    - Tags: eval_type="agentic", eval_date=today
    """

    if not ARIZE_SPACE_KEY or not ARIZE_API_KEY:
        print("WARNING: ARIZE_SPACE_KEY or ARIZE_API_KEY not set")
        print("Set environment variables to enable Arize upload:")
        print("  export ARIZE_SPACE_KEY=your_space_key")
        print("  export ARIZE_API_KEY=your_api_key")

        if not dry_run:
            print("\nRunning in dry-run mode (no upload)")
            dry_run = True

    try:
        from arize.pandas.logger import Client
        from arize.utils.types import ModelTypes, Environments, Schema
        import pandas as pd
    except ImportError:
        print("ERROR: arize package not installed")
        print("Install with: pip install arize")

        # Still show what would be uploaded
        print("\n" + "=" * 50)
        print("DRY RUN - Would upload these records:")
        print("=" * 50)

        for i, r in enumerate(results[:5]):
            print(f"\n[{i+1}] {r.get('scenario_id', 'unknown')}")
            print(f"    Prediction: {r.get('actual_verdict', 'N/A')}")
            print(f"    Actual: {r.get('expected_verdict', 'N/A')}")
            print(f"    Match: {r.get('match', 'N/A')}")
            print(f"    Confidence: {r.get('confidence', 'N/A')}")
            print(f"    Iterations: {r.get('iterations', 'N/A')}")

        if len(results) > 5:
            print(f"\n... and {len(results) - 5} more records")

        return

    # Convert to DataFrame
    records = []
    for r in results:
        prediction_id = str(uuid.uuid4())

        # Handle boolean/string match field
        match_val = r.get('match', 'False')
        if isinstance(match_val, str):
            match_bool = match_val.lower() == 'true'
        else:
            match_bool = bool(match_val)

        records.append({
            'prediction_id': prediction_id,
            'prediction_label': r.get('actual_verdict', 'UNKNOWN'),
            'actual_label': r.get('expected_verdict', 'UNKNOWN'),
            'framework': r.get('framework', 'unknown'),
            'confidence': float(r.get('confidence', 0)),
            'iterations': int(r.get('iterations', 1)),
            'risk_score': int(r.get('risk_score', 0)),
            'latency_ms': float(r.get('latency_ms', 0)),
            'chunks_retrieved': int(r.get('chunks_retrieved', 0)),
            'violations_count': int(r.get('violations_count', 0)),
            'match': match_bool,
            'error_type': r.get('error_type', ''),
            'scenario_id': r.get('scenario_id', ''),
            'eval_type': 'agentic',
            'eval_date': datetime.now().strftime('%Y-%m-%d')
        })

    df = pd.DataFrame(records)

    if dry_run:
        print("\n" + "=" * 50)
        print("DRY RUN - Would upload:")
        print("=" * 50)
        print(f"\nRecords: {len(df)}")
        print(f"Model ID: {MODEL_ID}")
        print(f"\nSample records:")
        print(df.head().to_string())
        return

    # Initialize Arize client
    arize_client = Client(
        space_key=ARIZE_SPACE_KEY,
        api_key=ARIZE_API_KEY
    )

    # Define schema
    schema = Schema(
        prediction_id_column_name="prediction_id",
        prediction_label_column_name="prediction_label",
        actual_label_column_name="actual_label",
        feature_column_names=[
            "framework",
            "confidence",
            "iterations",
            "risk_score",
            "latency_ms",
            "chunks_retrieved",
            "violations_count"
        ],
        tag_column_names=[
            "eval_type",
            "eval_date",
            "scenario_id",
            "error_type",
            "match"
        ]
    )

    # Log to Arize
    print(f"\nUploading {len(df)} records to Arize...")

    response = arize_client.log(
        dataframe=df,
        model_id=MODEL_ID,
        model_version=MODEL_VERSION,
        model_type=ModelTypes.SCORE_CATEGORICAL,
        environment=Environments.PRODUCTION,
        schema=schema
    )

    if response.status_code == 200:
        print(f"SUCCESS: Uploaded {len(df)} records to Arize")
        print(f"View at: https://app.arize.com/organizations/your-org/spaces/{ARIZE_SPACE_KEY}/models/{MODEL_ID}")
    else:
        print(f"ERROR: Upload failed with status {response.status_code}")
        print(response.text)


def print_summary(results: List[Dict]):
    """Print summary of results to be uploaded."""
    print("\n" + "=" * 50)
    print("UPLOAD SUMMARY")
    print("=" * 50)

    total = len(results)
    matches = sum(1 for r in results if str(r.get('match', '')).lower() == 'true')
    accuracy = matches / total if total > 0 else 0

    print(f"\nTotal Records: {total}")
    print(f"Accuracy: {accuracy:.1%}")

    # Framework breakdown
    frameworks = {}
    for r in results:
        fw = r.get('framework', 'unknown')
        if fw not in frameworks:
            frameworks[fw] = {'total': 0, 'match': 0}
        frameworks[fw]['total'] += 1
        if str(r.get('match', '')).lower() == 'true':
            frameworks[fw]['match'] += 1

    print(f"\nBy Framework:")
    for fw, data in sorted(frameworks.items()):
        acc = data['match'] / data['total'] if data['total'] > 0 else 0
        print(f"  {fw:15s}: {acc:.1%} ({data['match']}/{data['total']})")

    # Avg metrics
    avg_conf = sum(float(r.get('confidence', 0)) for r in results) / total
    avg_iter = sum(int(r.get('iterations', 1)) for r in results) / total
    avg_latency = sum(float(r.get('latency_ms', 0)) for r in results) / total

    print(f"\nAvg Confidence: {avg_conf:.2f}")
    print(f"Avg Iterations: {avg_iter:.1f}")
    print(f"Avg Latency: {avg_latency:.0f}ms")


def main():
    parser = argparse.ArgumentParser(description="Upload eval results to Arize")
    parser.add_argument('--results', type=str, default=RESULTS_PATH, help="Results CSV path")
    parser.add_argument('--dry-run', action='store_true', help="Don't actually upload")
    args = parser.parse_args()

    print("=" * 50)
    print("ARIZE UPLOAD")
    print("=" * 50)
    print(f"Results: {args.results}")
    print(f"Model ID: {MODEL_ID}")
    print(f"Dry run: {args.dry_run}")

    # Load results
    if not os.path.exists(args.results):
        print(f"\nERROR: Results file not found: {args.results}")
        print("Run agentic evals first: python run_agentic_evals.py")
        sys.exit(1)

    results = load_results(args.results)
    print(f"\nLoaded {len(results)} results")

    # Print summary
    print_summary(results)

    # Upload
    upload_to_arize(results, args.dry_run)


if __name__ == "__main__":
    main()
