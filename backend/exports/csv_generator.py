"""
CSV Export Generator for Sovereign V5

Exports violations as CSV table with columns:
framework, severity, article, evidence, remediation.
"""

import csv
import logging
from typing import List, Dict, Any
from io import StringIO

logger = logging.getLogger(__name__)


def generate_compliance_csv(violations: List[Dict[str, Any]]) -> str:
    """
    Generate Jira-compatible CSV export of compliance violations.

    Columns: Framework, Article, Severity, Priority, Description, Remediation Steps

    Args:
        violations: List of violation dictionaries.

    Returns:
        CSV content as string.
    """
    output = StringIO()

    # Define Jira-compatible CSV columns
    fieldnames = [
        'Framework',
        'Article',
        'Severity',
        'Priority',
        'Description',
        'Remediation Steps'
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    # Sort violations by severity for better readability
    severity_order = {'CRITICAL': 0, 'MAJOR': 1, 'MINOR': 2, 'NONE': 3}
    sorted_violations = sorted(
        violations,
        key=lambda v: severity_order.get(v.get('severity', 'NONE'), 4)
    )

    # Severity to Priority mapping
    severity_to_priority = {
        'CRITICAL': 'P0 (Immediate)',
        'MAJOR': 'P1 (30 days)',
        'MINOR': 'P2 (90 days)'
    }

    for violation in sorted_violations:
        severity = violation.get('severity', 'UNKNOWN')
        priority = severity_to_priority.get(severity, 'P2 (90 days)')

        # Combine remediation steps into single field with numbered list
        remediation_steps = violation.get('remediation_steps', [])
        if remediation_steps:
            remediation_text = '\n'.join([f"{i}. {step}" for i, step in enumerate(remediation_steps, 1)])
        else:
            remediation_text = 'No remediation provided'

        # Build description from evidence
        evidence = violation.get('evidence_quote', 'No evidence provided')
        description = f"Violation detected: {evidence}"

        row = {
            'Framework': violation.get('framework', 'Unknown').upper(),
            'Article': violation.get('article_violated', 'Unknown Article'),
            'Severity': severity,
            'Priority': priority,
            'Description': description,
            'Remediation Steps': remediation_text
        }

        writer.writerow(row)

    csv_content = output.getvalue()
    output.close()

    logger.info(f"Generated Jira-compatible CSV with {len(violations)} violations")
    return csv_content


def generate_summary_csv(
    violations: List[Dict[str, Any]],
    risk_score: int,
    frameworks: List[str]
) -> str:
    """
    Generate summary CSV with high-level statistics.

    Args:
        violations: List of violations.
        risk_score: Overall risk score.
        frameworks: Frameworks analyzed.

    Returns:
        Summary CSV content.
    """
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    # Header
    writer.writerow(['Metric', 'Value'])

    # Summary statistics
    writer.writerow(['Risk Score', risk_score])
    writer.writerow(['Total Violations', len(violations)])
    writer.writerow(['Frameworks Analyzed', ', '.join(f.upper() for f in frameworks)])

    # Breakdown by severity
    critical_count = sum(1 for v in violations if v.get('severity') == 'CRITICAL')
    major_count = sum(1 for v in violations if v.get('severity') == 'MAJOR')
    minor_count = sum(1 for v in violations if v.get('severity') == 'MINOR')

    writer.writerow(['Critical Violations', critical_count])
    writer.writerow(['Major Violations', major_count])
    writer.writerow(['Minor Violations', minor_count])

    # Breakdown by framework
    framework_counts = {}
    for v in violations:
        fw = v.get('framework', 'Unknown')
        framework_counts[fw] = framework_counts.get(fw, 0) + 1

    for fw, count in sorted(framework_counts.items()):
        writer.writerow([f'{fw} Violations', count])

    csv_content = output.getvalue()
    output.close()

    return csv_content
