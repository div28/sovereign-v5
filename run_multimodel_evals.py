#!/usr/bin/env python3
"""
Multi-Model Evaluation Runner for Sovereign V5

Run evaluation scenarios with different Claude models to compare performance.
Calls Claude API directly (not through Sovereign API).

Usage:
    python3 run_multimodel_evals.py --model sonnet --scenarios 60
    python3 run_multimodel_evals.py --model opus --scenarios 60
    python3 run_multimodel_evals.py --model haiku --scenarios 30

Requirements:
    pip install anthropic pandas
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import anthropic
    import pandas as pd
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install anthropic pandas")
    sys.exit(1)


# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

MODEL_MAPPING = {
    "haiku": "claude-3-5-haiku-20241022",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-0-20250514",
}

# Cost per 1K tokens (approximate)
COST_PER_SCENARIO = {
    "haiku": 0.25,
    "sonnet": 0.15,
    "opus": 0.30,
}

# Retry configuration
MAX_RETRIES = 2
RETRY_DELAY = 5
RATE_LIMIT_DELAY = 2


# =============================================================================
# COMPLIANCE ANALYSIS PROMPT
# =============================================================================

ANALYSIS_PROMPT = """You are a regulatory compliance expert. Analyze the following AI system description for {framework} violations.

## System Description
{description}

## Your Task
Determine if this system violates {framework} regulations.

## Response Format
Respond with a JSON object containing:
{{
    "violation_detected": true or false,
    "severity": "CRITICAL" or "MAJOR" or "MINOR" or "NONE",
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation of your analysis",
    "article_violated": "Specific article/section if violation found, or 'N/A'"
}}

## Key Considerations for {framework}:
{framework_guidance}

## Important Rules:
1. Only flag as violation if there is CLEAR evidence of non-compliance
2. If the system has safeguards (human review, appeals, etc.), consider it compliant
3. Gray areas should result in lower confidence (0.4-0.6)
4. Be conservative - when in doubt, lean toward compliant

Respond ONLY with the JSON object, no other text."""

FRAMEWORK_GUIDANCE = {
    "GDPR": """
- Article 22: Automated decisions require human review OR appeal mechanism
- Article 17: Users must be able to request data deletion within 30 days
- Article 32: Appropriate security measures (encryption, access controls) required
- If human oversight exists (>50% review rate), it's likely compliant
- If deletion mechanism exists, it's likely compliant""",

    "SOX": """
- Section 404: Internal controls must be documented and tested annually
- Section 302: CEO/CFO must certify financial reports
- Audit Trail: 7-year retention, immutable logs required
- If controls are tested regularly, it's likely compliant
- If certification process exists, it's likely compliant
- Compensating controls are acceptable for small companies""",

    "EU AI Act": """
- High-risk AI systems require conformity assessment
- Prohibited: Social scoring, real-time biometrics in public, subliminal manipulation
- Transparency: Users must know when interacting with AI
- If conformity assessment done, it's likely compliant
- Research settings may have exceptions""",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_api_key():
    """Get Anthropic API key from environment."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)
    return key


def normalize_framework(framework: str) -> str:
    """Normalize framework name."""
    framework_upper = framework.upper().strip()
    if "EU" in framework_upper or "AI ACT" in framework_upper:
        return "EU AI Act"
    return framework_upper


def call_claude(client, model: str, framework: str, description: str) -> dict:
    """
    Call Claude API for compliance analysis.

    Returns parsed response or error dict.
    """
    # Get framework guidance
    framework_key = "GDPR" if "GDPR" in framework.upper() else \
                    "SOX" if "SOX" in framework.upper() else \
                    "EU AI Act"
    guidance = FRAMEWORK_GUIDANCE.get(framework_key, "Analyze for regulatory compliance.")

    prompt = ANALYSIS_PROMPT.format(
        framework=framework,
        description=description,
        framework_guidance=guidance
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract text content
        content = response.content[0].text

        # Try to parse JSON from response
        try:
            # Find JSON in response (handle markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                # If no JSON found, parse from text
                return parse_text_response(content)
        except json.JSONDecodeError:
            return parse_text_response(content)

    except anthropic.RateLimitError:
        return {"error": True, "message": "Rate limited"}
    except anthropic.APITimeoutError:
        return {"error": True, "message": "Timeout"}
    except Exception as e:
        return {"error": True, "message": str(e)}


def parse_text_response(text: str) -> dict:
    """Parse compliance verdict from text if JSON parsing fails."""
    text_lower = text.lower()

    # Look for violation indicators
    violation_keywords = ["violation", "violates", "non-compliant", "breach", "fails to comply"]
    compliant_keywords = ["compliant", "no violation", "meets requirements", "satisfies"]

    violation_detected = any(kw in text_lower for kw in violation_keywords)
    is_compliant = any(kw in text_lower for kw in compliant_keywords)

    # If both found, check context more carefully
    if violation_detected and is_compliant:
        # Look for negation patterns
        if "no violation" in text_lower or "not a violation" in text_lower:
            violation_detected = False

    # Determine severity
    severity = "NONE"
    if violation_detected:
        if "critical" in text_lower:
            severity = "CRITICAL"
        elif "major" in text_lower:
            severity = "MAJOR"
        else:
            severity = "MINOR"

    return {
        "violation_detected": violation_detected,
        "severity": severity,
        "confidence": 0.75 if violation_detected else 0.80,
        "reasoning": text[:500],
        "article_violated": "Unknown"
    }


def call_claude_with_retry(client, model: str, framework: str,
                           description: str, test_id: str) -> dict:
    """Call Claude with retry logic."""
    for attempt in range(MAX_RETRIES + 1):
        result = call_claude(client, model, framework, description)

        if not result.get("error"):
            return result

        if attempt < MAX_RETRIES:
            print(f"    Retry {attempt + 1}/{MAX_RETRIES} for {test_id}...")
            time.sleep(RETRY_DELAY)

    return result


def load_scenarios(input_csv: str, num_scenarios: int) -> list:
    """Load scenarios from golden dataset."""
    if not os.path.exists(input_csv):
        print(f"ERROR: {input_csv} not found")
        sys.exit(1)

    df = pd.read_csv(input_csv)
    df = df.head(num_scenarios)

    scenarios = []
    for _, row in df.iterrows():
        scenarios.append({
            "test_id": row.get("test_id", "UNKNOWN"),
            "framework": row.get("framework", "GDPR"),
            "scenario_type": row.get("scenario_type", "violation"),
            "policy_summary": row.get("policy_summary", ""),
            "ai_system_description": row.get("ai_system_description", ""),
            "expected_verdict": row.get("expected_verdict", "VIOLATION"),
            "expected_severity": row.get("expected_severity", "CRITICAL"),
        })

    return scenarios


def save_results(results: list, output_csv: str):
    """Save results to CSV."""
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "test_id", "framework", "scenario_type", "expected_verdict",
        "actual_verdict", "match", "model_used", "confidence",
        "severity", "reasoning_excerpt", "timestamp"
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {output_csv}")


def print_summary(results: list, model_name: str, model_id: str):
    """Print evaluation summary."""
    matches = sum(1 for r in results if r.get("match") == "TRUE")
    total = len(results)
    match_pct = (matches / total * 100) if total > 0 else 0

    print("\n" + "=" * 50)
    print(f"    {model_name.upper()} RESULTS")
    print("=" * 50)
    print(f"Total Scenarios: {total}")
    print(f"Matches: {matches} ({match_pct:.1f}%)")
    print(f"Mismatches: {total - matches}")
    print(f"Model: {model_id}")
    print(f"Estimated Cost: ${total * COST_PER_SCENARIO.get(model_name, 0.20):.2f}")
    print("=" * 50)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run multi-model compliance evaluations"
    )
    parser.add_argument(
        "--model",
        required=True,
        choices=["haiku", "sonnet", "opus"],
        help="Claude model to use"
    )
    parser.add_argument(
        "--scenarios",
        type=int,
        default=60,
        help="Number of scenarios to run (default: 60)"
    )
    parser.add_argument(
        "--input",
        default="evals/golden_dataset.csv",
        help="Input CSV path"
    )
    parser.add_argument(
        "--output-dir",
        default="evals",
        help="Output directory for results"
    )

    args = parser.parse_args()

    # Get model ID
    model_id = MODEL_MAPPING.get(args.model)
    if not model_id:
        print(f"ERROR: Unknown model {args.model}")
        sys.exit(1)

    # Initialize client
    api_key = get_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    # Print header
    print("=" * 50)
    print("    MULTI-MODEL EVALUATION RUNNER")
    print("=" * 50)
    print(f"Model: {args.model} ({model_id})")
    print(f"Scenarios: {args.scenarios}")
    print(f"Input: {args.input}")
    print(f"Est. Cost: ${args.scenarios * COST_PER_SCENARIO.get(args.model, 0.20):.2f}")
    print("=" * 50)
    print()

    # Load scenarios
    print(f"Loading scenarios from {args.input}...")
    scenarios = load_scenarios(args.input, args.scenarios)
    print(f"Loaded {len(scenarios)} scenarios\n")

    # Run evaluations
    results = []
    start_time = time.time()

    for i, scenario in enumerate(scenarios, 1):
        test_id = scenario["test_id"]
        framework = normalize_framework(scenario["framework"])

        print(f"[{i}/{len(scenarios)}] {test_id} ({framework})")

        # Combine policy and AI description
        description = f"""Policy Summary: {scenario['policy_summary']}

AI System Description: {scenario['ai_system_description']}"""

        # Call Claude
        response = call_claude_with_retry(
            client, model_id, framework, description, test_id
        )

        # Extract results
        if response.get("error"):
            actual_verdict = "ERROR"
            confidence = 0
            severity = "N/A"
            reasoning = response.get("message", "API error")
        else:
            violation = response.get("violation_detected", False)
            actual_verdict = "VIOLATION" if violation else "COMPLIANT"
            confidence = response.get("confidence", 0.75)
            severity = response.get("severity", "NONE")
            reasoning = response.get("reasoning", "")[:200]

        # Compare with expected
        expected = scenario["expected_verdict"].upper()
        match = expected == actual_verdict

        # Build result
        result = {
            "test_id": test_id,
            "framework": scenario["framework"],
            "scenario_type": scenario["scenario_type"],
            "expected_verdict": expected,
            "actual_verdict": actual_verdict,
            "match": "TRUE" if match else "FALSE",
            "model_used": args.model,
            "confidence": f"{confidence:.2f}" if isinstance(confidence, float) else confidence,
            "severity": severity,
            "reasoning_excerpt": reasoning,
            "timestamp": datetime.now().isoformat()
        }
        results.append(result)

        # Status
        status = "MATCH" if match else "MISMATCH"
        print(f"    → {actual_verdict} (expected: {expected}) [{status}]")

        # Rate limit delay
        time.sleep(RATE_LIMIT_DELAY)

    # Save results
    output_csv = f"{args.output_dir}/multimodel_results_{args.model}.csv"
    save_results(results, output_csv)

    # Print summary
    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.1f} seconds")
    print_summary(results, args.model, model_id)

    # Comparison hint
    print("\nTo compare models, run with different --model flags:")
    print("  python3 run_multimodel_evals.py --model haiku --scenarios 60")
    print("  python3 run_multimodel_evals.py --model sonnet --scenarios 60")
    print("  python3 run_multimodel_evals.py --model opus --scenarios 60")


if __name__ == "__main__":
    main()
