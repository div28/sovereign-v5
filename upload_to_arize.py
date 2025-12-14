#!/usr/bin/env python3
"""
Arize Upload Script for Sovereign V5 Multi-Model Evaluations

Combines evaluation results from all 3 models and uploads to Arize dashboard
for visualization and model comparison.

Usage:
    python3 upload_to_arize.py

Environment Variables Required:
    ARIZE_ORG_KEY - Your Arize organization key
    ARIZE_SPACE_KEY - Your Arize space key

Input Files:
    evals/multimodel_results_haiku.csv (30 scenarios)
    evals/multimodel_results_sonnet.csv (60 scenarios)
    evals/multimodel_results_opus.csv (60 scenarios)

Output:
    evals/combined_multimodel_results.csv (150 total rows)
    Dataset uploaded to Arize: "sovereign-compliance-evals"

Requirements:
    pip install arize pandas
"""

import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
    from arize.pandas.logger import Client
    from arize.utils.types import ModelTypes, Environments, Schema
except ImportError as e:
    print("Missing dependencies. Install with:")
    print("  pip install arize pandas")
    print(f"\nError: {e}")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

EVAL_DIR = "evals"
OUTPUT_FILE = f"{EVAL_DIR}/combined_multimodel_results.csv"

# Input CSV files
INPUT_FILES = {
    "haiku": f"{EVAL_DIR}/multimodel_results_haiku.csv",
    "sonnet": f"{EVAL_DIR}/multimodel_results_sonnet.csv",
    "opus": f"{EVAL_DIR}/multimodel_results_opus.csv",
}

# Arize configuration
ARIZE_MODEL_ID = "sovereign-compliance-evals"
ARIZE_MODEL_VERSION = "v5.0"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_arize_keys():
    """Get Arize API keys from environment."""
    org_key = os.environ.get("ARIZE_ORG_KEY")
    space_key = os.environ.get("ARIZE_SPACE_KEY")

    if not org_key:
        print("ERROR: ARIZE_ORG_KEY environment variable not set")
        print("Set it with: export ARIZE_ORG_KEY='your-org-key'")
        return None, None

    if not space_key:
        print("ERROR: ARIZE_SPACE_KEY environment variable not set")
        print("Set it with: export ARIZE_SPACE_KEY='your-space-key'")
        return None, None

    return org_key, space_key


def load_and_combine_csvs():
    """Load all evaluation CSVs and combine into single DataFrame."""
    dfs = []
    total_loaded = 0

    for model_name, filepath in INPUT_FILES.items():
        if not os.path.exists(filepath):
            print(f"  Warning: {filepath} not found, skipping...")
            continue

        df = pd.read_csv(filepath)
        row_count = len(df)
        dfs.append(df)
        total_loaded += row_count
        print(f"  Loaded {filepath}: {row_count} rows")

    if not dfs:
        print("ERROR: No evaluation files found!")
        print("Run evaluations first with:")
        print("  python3 run_multimodel_evals.py --model haiku --scenarios 30")
        print("  python3 run_multimodel_evals.py --model sonnet --scenarios 60")
        print("  python3 run_multimodel_evals.py --model opus --scenarios 60")
        return None

    # Combine all DataFrames
    combined = pd.concat(dfs, ignore_index=True)

    # Select and rename columns for Arize
    columns_to_keep = [
        "test_id",
        "framework",
        "expected_verdict",
        "actual_verdict",
        "match",
        "model_used",
        "confidence",
    ]

    # Keep only columns that exist
    available_cols = [c for c in columns_to_keep if c in combined.columns]
    combined = combined[available_cols]

    # Convert match to boolean string if needed
    if "match" in combined.columns:
        combined["match"] = combined["match"].astype(str).str.upper()

    # Convert confidence to float
    if "confidence" in combined.columns:
        combined["confidence"] = pd.to_numeric(combined["confidence"], errors="coerce")

    return combined


def save_combined_csv(df, output_path):
    """Save combined DataFrame to CSV."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"  Saved combined CSV: {output_path}")


def upload_to_arize(df, org_key, space_key):
    """Upload DataFrame to Arize dashboard."""
    print("\nInitializing Arize client...")

    # Initialize client
    arize_client = Client(
        space_key=space_key,
        api_key=org_key,
    )

    # Create unique prediction IDs
    df["prediction_id"] = [
        f"{row['test_id']}_{row['model_used']}_{i}"
        for i, row in df.iterrows()
    ]

    # Add timestamp
    df["prediction_ts"] = datetime.now()

    # Define schema for Arize
    # Features: framework, model_used, confidence
    # Prediction: actual_verdict
    # Actual: expected_verdict (ground truth)

    schema = Schema(
        prediction_id_column_name="prediction_id",
        timestamp_column_name="prediction_ts",
        prediction_label_column_name="actual_verdict",
        actual_label_column_name="expected_verdict",
        feature_column_names=["framework", "model_used", "confidence", "test_id"],
        tag_column_names=["match"],
    )

    print(f"Uploading {len(df)} records to Arize...")
    print(f"  Model ID: {ARIZE_MODEL_ID}")
    print(f"  Model Version: {ARIZE_MODEL_VERSION}")

    # Log the DataFrame
    response = arize_client.log(
        dataframe=df,
        model_id=ARIZE_MODEL_ID,
        model_version=ARIZE_MODEL_VERSION,
        model_type=ModelTypes.SCORE_CATEGORICAL,
        environment=Environments.PRODUCTION,
        schema=schema,
    )

    return response


def print_summary(df):
    """Print summary statistics."""
    print("\n" + "=" * 50)
    print("    SUMMARY")
    print("=" * 50)

    # Overall stats
    total = len(df)
    matches = len(df[df["match"] == "TRUE"])
    match_pct = (matches / total * 100) if total > 0 else 0

    print(f"Total Rows: {total}")
    print(f"Overall Accuracy: {matches}/{total} ({match_pct:.1f}%)")

    # Per-model stats
    print("\nPer-Model Breakdown:")
    for model in ["haiku", "sonnet", "opus"]:
        model_df = df[df["model_used"] == model]
        if len(model_df) > 0:
            model_matches = len(model_df[model_df["match"] == "TRUE"])
            model_total = len(model_df)
            model_pct = (model_matches / model_total * 100)
            print(f"  {model.upper()}: {model_matches}/{model_total} ({model_pct:.1f}%)")

    # Per-framework stats
    print("\nPer-Framework Breakdown:")
    for framework in df["framework"].unique():
        fw_df = df[df["framework"] == framework]
        fw_matches = len(fw_df[fw_df["match"] == "TRUE"])
        fw_total = len(fw_df)
        fw_pct = (fw_matches / fw_total * 100) if fw_total > 0 else 0
        print(f"  {framework}: {fw_matches}/{fw_total} ({fw_pct:.1f}%)")

    print("=" * 50)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 50)
    print("    ARIZE UPLOAD SCRIPT")
    print("=" * 50)
    print()

    # Step 1: Load and combine CSVs
    print("Step 1: Loading evaluation CSVs...")
    df = load_and_combine_csvs()

    if df is None:
        sys.exit(1)

    print(f"\n  Total combined rows: {len(df)}")

    # Step 2: Save combined CSV
    print("\nStep 2: Saving combined CSV...")
    save_combined_csv(df, OUTPUT_FILE)

    # Step 3: Print summary
    print_summary(df)

    # Step 4: Upload to Arize
    print("\nStep 3: Uploading to Arize...")
    org_key, space_key = get_arize_keys()

    if not org_key or not space_key:
        print("\n⚠️  Skipping Arize upload (missing API keys)")
        print("Set environment variables and re-run to upload:")
        print("  export ARIZE_ORG_KEY='your-org-key'")
        print("  export ARIZE_SPACE_KEY='your-space-key'")
        print(f"\n✅ Combined CSV created: {OUTPUT_FILE}")
        print(f"✅ Total rows: {len(df)}")
        return

    try:
        response = upload_to_arize(df, org_key, space_key)

        if response.status_code == 200:
            print("\n✅ Combined CSV created: " + OUTPUT_FILE)
            print(f"✅ Total rows: {len(df)}")
            print("✅ Dataset uploaded to Arize")
            print(f"\n📊 Dashboard: https://app.arize.com/organizations/home/spaces")
            print(f"   Model: {ARIZE_MODEL_ID}")
        else:
            print(f"\n❌ Upload failed with status: {response.status_code}")
            print(f"   Response: {response.text}")

    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        print(f"\n✅ Combined CSV created: {OUTPUT_FILE}")
        print("   You can manually import this CSV to Arize")


if __name__ == "__main__":
    main()
