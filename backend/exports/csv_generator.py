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
    Generate CSV export of compliance violations.

    Args:
        violations: List of violation dictionaries.

    Returns:
        CSV content as string.
    """
    output = StringIO()

    # Define CSV columns
    fieldnames = [
        'framework',
        'severity',
        'article',
        'focus_area',
        'evidence',
        'remediation',
        'confidence',
        'judge_id'
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    # Sort violations by severity for better readability
    severity_order = {'CRITICAL': 0, 'MAJOR': 1, 'MINOR': 2, 'NONE': 3}
    sorted_violations = sorted(
        violations,
        key=lambda v: severity_order.get(v.get('severity', 'NONE'), 4)
    )

    for violation in sorted_violations:
        # Combine remediation steps into single field
        remediation_steps = violation.get('remediation_steps', [])
        remediation_text = ' | '.join(remediation_steps) if remediation_steps else 'No remediation provided'

        row = {
            'framework': violation.get('framework', 'Unknown'),
            'severity': violation.get('severity', 'UNKNOWN'),
            'article': violation.get('article_violated', 'Unknown Article'),
            'focus_area': violation.get('focus_area', 'Unknown'),
            'evidence': violation.get('evidence_quote', 'No evidence provided'),
            'remediation': remediation_text,
            'confidence': f"{violation.get('confidence', 0.0):.2f}",
            'judge_id': violation.get('judge_id', 'unknown')
        }

        writer.writerow(row)

    csv_content = output.getvalue()
    output.close()

    logger.info(f"Generated CSV with {len(violations)} violations")
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
