#!/usr/bin/env python3
"""
Test script for GDPR Article 22 Judge

Tests the judge with a clear automated decision-making violation:
A hiring AI system that automatically rejects candidates without human review.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


def test_article_22_violation():
    """Test detection of a clear Article 22 violation."""

    print("=" * 60)
    print("GDPR Article 22 Judge Test")
    print("=" * 60)

    # Clear violation scenario: Hiring AI with no human review
    test_submission = """
    AI-Powered Hiring System Description:

    Our company has deployed an advanced AI recruitment platform called "HireBot Pro"
    that streamlines the entire hiring process. Here's how it works:

    1. Resume Screening: The AI automatically scans all incoming resumes and scores
       candidates on a scale of 1-100 based on keywords, experience patterns, and
       educational background.

    2. Automated Rejection: Candidates scoring below 65 are automatically sent a
       rejection email. This happens instantly without any human review. Last month,
       we automatically rejected 2,847 applicants this way.

    3. Video Interview Analysis: Shortlisted candidates complete a one-way video
       interview. Our AI analyzes facial expressions, speech patterns, and word
       choice to generate a "culture fit" score.

    4. Final Decision: The system automatically extends job offers to candidates
       who score above 85 on all metrics. No human is involved in this decision.

    5. Data Processing: We store all candidate data including video recordings,
       facial analysis results, and psychological assessments indefinitely for
       model improvement.

    Benefits: We've reduced hiring time by 90% and eliminated human bias from
    the process. The AI makes all employment decisions autonomously, ensuring
    consistency and efficiency.
    """

    print("\n📋 Test Submission:")
    print("-" * 40)
    print(test_submission.strip())
    print("-" * 40)

    # Initialize judge
    print("\n🔄 Initializing GDPR Article 22 Judge...")

    try:
        from backend.judges import GDPRArticle22Judge

        judge = GDPRArticle22Judge()
        print(f"✅ Judge initialized: {judge}")

        # For testing without RAG, use empty chunks
        # In production, these would come from the RAG engine
        mock_chunks = [
            {
                "text": """GDPR Article 22 - Automated individual decision-making, including profiling:
                1. The data subject shall have the right not to be subject to a decision based solely
                on automated processing, including profiling, which produces legal effects concerning
                him or her or similarly significantly affects him or her.""",
                "metadata": {"article": "Article 22", "section": "Paragraph 1"}
            },
            {
                "text": """Decisions based solely on automated processing are permitted only if the decision:
                (a) is necessary for entering into, or performance of, a contract;
                (b) is authorised by Union or Member State law; or
                (c) is based on the data subject's explicit consent.
                In cases (a) and (c), the controller must implement suitable safeguards including
                the right to obtain human intervention.""",
                "metadata": {"article": "Article 22", "section": "Paragraphs 2-3"}
            }
        ]

        print("\n🔍 Evaluating submission for Article 22 violations...")
        result = judge.evaluate(
            submission=test_submission,
            retrieved_chunks=mock_chunks
        )

        print("\n" + "=" * 60)
        print("📊 EVALUATION RESULTS")
        print("=" * 60)

        if result:
            print(f"\n🚨 VIOLATION DETECTED!")
            print(f"\n  Severity:        {result.get('severity', 'N/A')}")
            print(f"  Article:         {result.get('article_violated', 'N/A')}")
            print(f"  Confidence:      {result.get('confidence', 0):.0%}")
            print(f"  Judge ID:        {result.get('judge_id', 'N/A')}")

            print(f"\n  📝 Evidence Quote:")
            evidence = result.get('evidence_quote', 'N/A')
            # Wrap long evidence
            if len(evidence) > 70:
                words = evidence.split()
                lines = []
                current_line = "     "
                for word in words:
                    if len(current_line) + len(word) > 70:
                        lines.append(current_line)
                        current_line = "     " + word
                    else:
                        current_line += " " + word
                lines.append(current_line)
                print("\n".join(lines))
            else:
                print(f"     {evidence}")

            print(f"\n  🔧 Remediation Steps:")
            for i, step in enumerate(result.get('remediation_steps', []), 1):
                print(f"     {i}. {step}")

            # Verify expected results
            print("\n" + "-" * 60)
            print("✅ TEST VALIDATION:")

            expected_severity = "CRITICAL"
            actual_severity = result.get('severity', '')

            if actual_severity == expected_severity:
                print(f"   ✓ Severity is {expected_severity} as expected")
            else:
                print(f"   ✗ Expected {expected_severity}, got {actual_severity}")

            if result.get('violation_detected'):
                print("   ✓ Violation correctly detected")
            else:
                print("   ✗ Violation should have been detected")

            if "22" in result.get('article_violated', ''):
                print("   ✓ Article 22 correctly identified")
            else:
                print("   ✗ Article 22 should be identified")

        else:
            print("\n❌ No violation detected (unexpected for this test case)")
            print("   This test case should detect a CRITICAL violation.")

        print("\n" + "=" * 60)
        print("Test complete!")

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Check for required API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set in environment")
        print("   Create a .env file or export the variable")
        sys.exit(1)

    test_article_22_violation()
