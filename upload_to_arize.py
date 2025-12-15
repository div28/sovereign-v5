#!/usr/bin/env python3
"""
Arize Upload Script for Sovereign V5 Multi-Model Evaluations

Combines evaluation results from all 3 models and uploads to Arize dashboard
for visualization and model comparison.

Usage:
    python3 upload_to_arize.py

Environment Variables Required:
    ARIZE_API_KEY - Your Arize API key (from Settings > API Keys)
    ARIZE_SPACE_ID - Your Arize space ID (from Settings > Space)

Input Files:
    evals/multimodel_results_haiku.csv (30 scenarios)
    evals/multimodel_results_sonnet.csv (60 scenarios)
    evals/multimodel_results_opus.csv (60 scenarios)

Output:
    evals/combined_multimodel_results.csv (150 total rows, original)
    evals/combined_multimodel_results_enriched.csv (with added dimensions)
    Dataset uploaded to Arize: "sovereign-compliance-evals"

Enriched Dimensions:
    - severity: CRITICAL, MAJOR, MEDIUM, MINOR
    - violation_category: Privacy, Security, Automation, Transparency, etc.
    - confidence_bucket: Low (<80%), Medium (80-90%), High (90-95%), Very High (>95%)
    - test_category: violation, compliant, gray_area

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
ENRICHED_OUTPUT_FILE = f"{EVAL_DIR}/combined_multimodel_results_enriched.csv"

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
# ENRICHMENT MAPPINGS
# =============================================================================

# Severity mapping based on test_id patterns
SEVERITY_RULES = {
    # CRITICAL - Fundamental rights violations
    "ART22": "CRITICAL",      # Automated decision-making
    "ART9": "CRITICAL",       # Special category data
    "CONSENT": "CRITICAL",    # Consent violations
    "S404": "CRITICAL",       # SOX internal controls
    "PROHIBITED": "CRITICAL", # EU AI Act prohibited
    "BIOMETRIC": "CRITICAL",  # Biometric data
    "SOCIAL_SCORE": "CRITICAL",

    # MAJOR - Significant compliance gaps
    "ART17": "MAJOR",         # Right to erasure
    "ART32": "MAJOR",         # Security of processing
    "S302": "MAJOR",          # SOX certification
    "AUDIT": "MAJOR",         # Audit trail
    "BIAS": "MAJOR",          # Fairness/bias
    "HIGH_RISK": "MAJOR",     # EU AI Act high-risk
    "TRANSPARENCY": "MAJOR",

    # MEDIUM - Moderate issues
    "ART13": "MEDIUM",        # Information provision
    "ART14": "MEDIUM",        # Fair processing
    "DOCUMENTATION": "MEDIUM",
    "RETENTION": "MEDIUM",
    "CONFORMITY": "MEDIUM",

    # MINOR - Low severity
    "NOTICE": "MINOR",
    "PROCEDURAL": "MINOR",
}

# Category mapping based on test_id patterns
CATEGORY_RULES = {
    # Privacy
    "ART17": "Privacy",
    "ART9": "Privacy",
    "CONSENT": "Privacy",
    "ERASURE": "Privacy",
    "RETENTION": "Privacy",

    # Automation
    "ART22": "Automation",
    "AUTOMATED": "Automation",
    "DECISION": "Automation",

    # Security
    "ART32": "Security",
    "ENCRYPTION": "Security",
    "ACCESS": "Security",
    "AUDIT": "Security",

    # Transparency
    "ART13": "Transparency",
    "ART14": "Transparency",
    "TRANSPARENCY": "Transparency",
    "NOTICE": "Transparency",
    "DISCLOSURE": "Transparency",

    # Fairness
    "BIAS": "Fairness",
    "DISCRIMINATION": "Fairness",
    "FAIRNESS": "Fairness",

    # Governance
    "S404": "Governance",
    "S302": "Governance",
    "SOX": "Governance",
    "CERTIFICATION": "Governance",
    "CONTROL": "Governance",

    # AI Safety
    "PROHIBITED": "AI_Safety",
    "HIGH_RISK": "AI_Safety",
    "BIOMETRIC": "AI_Safety",
    "SOCIAL_SCORE": "AI_Safety",
    "CONFORMITY": "AI_Safety",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_arize_credentials():
    """Get Arize API credentials from environment."""
    api_key = os.environ.get("ARIZE_API_KEY")
    space_id = os.environ.get("ARIZE_SPACE_ID")

    if not api_key:
        print("ERROR: ARIZE_API_KEY environment variable not set")
        print("Set it with: export ARIZE_API_KEY='your-api-key'")
        print("Get your API key from: https://app.arize.com/admin/api-keys")
        return None, None

    if not space_id:
        print("ERROR: ARIZE_SPACE_ID environment variable not set")
        print("Set it with: export ARIZE_SPACE_ID='your-space-id'")
        print("Get your Space ID from: https://app.arize.com/admin/space")
        return None, None

    return api_key, space_id


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


def get_severity(test_id: str) -> str:
    """Derive severity from test_id pattern."""
    test_id_upper = test_id.upper()
    for pattern, severity in SEVERITY_RULES.items():
        if pattern in test_id_upper:
            return severity
    return "MEDIUM"  # Default


def get_category(test_id: str, framework: str) -> str:
    """Derive violation category from test_id and framework."""
    test_id_upper = test_id.upper()

    # Check pattern rules first
    for pattern, category in CATEGORY_RULES.items():
        if pattern in test_id_upper:
            return category

    # Fall back to framework-based defaults
    framework_upper = framework.upper() if framework else ""
    if "GDPR" in framework_upper:
        return "Privacy"
    elif "SOX" in framework_upper:
        return "Governance"
    elif "EU" in framework_upper or "AI" in framework_upper:
        return "AI_Safety"

    return "Other"


def get_confidence_bucket(confidence: float) -> str:
    """Bucket confidence into categories."""
    if pd.isna(confidence):
        return "Unknown"
    conf = float(confidence)
    if conf < 0.80:
        return "Low (<80%)"
    elif conf < 0.90:
        return "Medium (80-90%)"
    elif conf < 0.95:
        return "High (90-95%)"
    else:
        return "Very High (>95%)"


def get_test_category(test_id: str, expected_verdict: str) -> str:
    """Categorize test as violation, compliant, or gray_area."""
    test_id_upper = test_id.upper()

    # Check for gray area indicators
    if "GRAY" in test_id_upper or "EDGE" in test_id_upper or "AMBIG" in test_id_upper:
        return "gray_area"

    # Check expected verdict
    if expected_verdict:
        verdict_upper = str(expected_verdict).upper()
        if "VIOLATION" in verdict_upper:
            return "violation"
        elif "COMPLIANT" in verdict_upper:
            return "compliant"

    # Check test_id for hints
    if "_V" in test_id_upper or "VIOLATION" in test_id_upper:
        return "violation"
    elif "_C" in test_id_upper or "COMPLIANT" in test_id_upper:
        return "compliant"

    return "unknown"


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add enriched dimensions to DataFrame."""
    print("\nStep 3: Enriching data with additional dimensions...")

    # Create a copy to avoid modifying original
    enriched = df.copy()

    # Add severity
    enriched["severity"] = enriched["test_id"].apply(get_severity)
    severity_counts = enriched["severity"].value_counts()
    print(f"  Added severity: {dict(severity_counts)}")

    # Add violation_category
    enriched["violation_category"] = enriched.apply(
        lambda row: get_category(row["test_id"], row.get("framework", "")),
        axis=1
    )
    category_counts = enriched["violation_category"].value_counts()
    print(f"  Added violation_category: {dict(category_counts)}")

    # Add confidence_bucket
    enriched["confidence_bucket"] = enriched["confidence"].apply(get_confidence_bucket)
    bucket_counts = enriched["confidence_bucket"].value_counts()
    print(f"  Added confidence_bucket: {dict(bucket_counts)}")

    # Add test_category
    enriched["test_category"] = enriched.apply(
        lambda row: get_test_category(row["test_id"], row.get("expected_verdict", "")),
        axis=1
    )
    test_cat_counts = enriched["test_category"].value_counts()
    print(f"  Added test_category: {dict(test_cat_counts)}")

    return enriched


def upload_to_arize(df, api_key, space_id):
    """Upload DataFrame to Arize dashboard."""
    print("\nInitializing Arize client...")

    # Initialize client with correct parameters
    arize_client = Client(
        api_key=api_key,
        space_id=space_id,
    )

    # Create unique prediction IDs
    df["prediction_id"] = [
        f"{row['test_id']}_{row['model_used']}_{i}"
        for i, row in df.iterrows()
    ]

    # Add timestamp
    df["prediction_ts"] = datetime.now()

    # Define schema for Arize
    # Features: All filterable dimensions (model_used, framework, etc.)
    # Prediction: actual_verdict
    # Actual: expected_verdict (ground truth)
    # Tags: Additional metadata for grouping

    # Core features - these MUST be filterable in dashboard
    feature_cols = []

    # Add core columns as features (for filtering)
    core_features = ["model_used", "framework", "test_id"]
    for col in core_features:
        if col in df.columns:
            feature_cols.append(col)

    # Add confidence as numeric feature
    if "confidence" in df.columns:
        feature_cols.append("confidence")

    # Add enriched dimensions as features (for filtering)
    enriched_cols = ["severity", "violation_category", "confidence_bucket", "test_category"]
    for col in enriched_cols:
        if col in df.columns:
            feature_cols.append(col)

    # Tags for additional metadata
    tag_cols = []
    if "match" in df.columns:
        tag_cols.append("match")

    print(f"  Features (filterable): {feature_cols}")
    print(f"  Tags: {tag_cols}")

    schema = Schema(
        prediction_id_column_name="prediction_id",
        timestamp_column_name="prediction_ts",
        prediction_label_column_name="actual_verdict",
        actual_label_column_name="expected_verdict",
        feature_column_names=feature_cols,
        tag_column_names=tag_cols if tag_cols else None,
    )

    print(f"\nUploading {len(df)} records to Arize...")
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

    # Step 2: Save combined CSV (original)
    print("\nStep 2: Saving combined CSV...")
    save_combined_csv(df, OUTPUT_FILE)

    # Step 3: Enrich with additional dimensions
    df_enriched = enrich_dataframe(df)

    # Step 4: Save enriched CSV
    print("\nStep 4: Saving enriched CSV...")
    save_combined_csv(df_enriched, ENRICHED_OUTPUT_FILE)

    # Step 5: Print summary
    print_summary(df_enriched)

    # Step 6: Upload to Arize (using enriched data)
    print("\nStep 5: Uploading to Arize...")
    api_key, space_id = get_arize_credentials()

    if not api_key or not space_id:
        print("\n⚠️  Skipping Arize upload (missing credentials)")
        print("Set environment variables and re-run to upload:")
        print("  export ARIZE_API_KEY='your-api-key'")
        print("  export ARIZE_SPACE_ID='your-space-id'")
        print(f"\n✅ Combined CSV created: {OUTPUT_FILE}")
        print(f"✅ Enriched CSV created: {ENRICHED_OUTPUT_FILE}")
        print(f"✅ Total rows: {len(df_enriched)}")
        return

    try:
        response = upload_to_arize(df_enriched, api_key, space_id)

        if response.status_code == 200:
            print("\n✅ Combined CSV created: " + OUTPUT_FILE)
            print(f"✅ Enriched CSV created: {ENRICHED_OUTPUT_FILE}")
            print(f"✅ Total rows: {len(df_enriched)}")
            print("✅ Dataset uploaded to Arize (with enriched dimensions)")
            print(f"\n📊 Dashboard: https://app.arize.com/organizations/home/spaces")
            print(f"   Model: {ARIZE_MODEL_ID}")
            print("\n   New dimensions available for segmentation:")
            print("   - severity: CRITICAL, MAJOR, MEDIUM, MINOR")
            print("   - violation_category: Privacy, Security, Automation, etc.")
            print("   - confidence_bucket: Low, Medium, High, Very High")
            print("   - test_category: violation, compliant, gray_area")
        else:
            print(f"\n❌ Upload failed with status: {response.status_code}")
            print(f"   Response: {response.text}")

    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        print(f"\n✅ Combined CSV created: {OUTPUT_FILE}")
        print(f"✅ Enriched CSV created: {ENRICHED_OUTPUT_FILE}")
        print("   You can manually import the enriched CSV to Arize")


if __name__ == "__main__":
    main()
