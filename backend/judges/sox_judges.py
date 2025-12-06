"""
SOX Compliance Judges for Sovereign V5

Specialized judges for detecting Sarbanes-Oxley Act violations.
Each judge focuses on a specific section or requirement.
"""

import logging
from typing import Dict, List, Any

from .base_judge import BaseComplianceJudge

logger = logging.getLogger(__name__)


class SOXSection404Judge(BaseComplianceJudge):
    """
    Judge for SOX Section 404 - Internal Control Assessment.

    Detects violations related to:
    - Missing internal controls over financial reporting
    - Inadequate control documentation
    - Lack of control testing procedures
    - Missing management assessment of controls
    """

    EVALUATION_PROMPT = """You are a SOX compliance expert specializing in Section 404 (Internal Control Assessment).

## SOX Section 404 Requirements

Section 404 requires:
1. **Management Assessment**: Annual assessment of internal control over financial reporting (ICFR)
2. **Control Documentation**: Documented policies and procedures for financial controls
3. **Testing Procedures**: Regular testing of control effectiveness
4. **Auditor Attestation**: External auditor must attest to management's assessment
5. **Material Weakness Reporting**: Identification and disclosure of material weaknesses

Key controls include:
- Segregation of duties
- Access controls to financial systems
- Change management procedures
- Reconciliation processes
- Approval workflows

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze for SOX Section 404 violations:
1. **Missing Controls**: No documented internal controls for financial processes
2. **Inadequate Documentation**: Controls exist but are not properly documented
3. **No Testing**: Controls are not regularly tested for effectiveness
4. **Segregation Issues**: Same person can initiate, approve, and record transactions
5. **Access Control Gaps**: Unrestricted access to financial systems/data

Severity:
- CRITICAL: No internal controls or complete lack of segregation of duties
- MAJOR: Missing documentation or testing procedures
- MINOR: Incomplete documentation or infrequent testing"""

    def __init__(self, api_key: str = None):
        """Initialize the SOX Section 404 judge."""
        super().__init__(
            framework="SOX",
            focus_area="internal control assessment",
            model="claude-3-5-haiku-20241022",
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """Build the Section 404 evaluation prompt."""
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )


class SOXSection302Judge(BaseComplianceJudge):
    """
    Judge for SOX Section 302 - Corporate Responsibility for Financial Reports.

    Detects violations related to:
    - CEO/CFO certification requirements
    - Disclosure controls and procedures
    - Fraud disclosure obligations
    - Significant changes in internal controls
    """

    EVALUATION_PROMPT = """You are a SOX compliance expert specializing in Section 302 (Corporate Responsibility).

## SOX Section 302 Requirements

Section 302 requires CEO and CFO to certify:
1. **Report Accuracy**: Financial statements fairly present company's financial condition
2. **Disclosure Controls**: Adequate controls ensure material information is disclosed
3. **Control Design**: Disclosure controls are designed to ensure accuracy
4. **Control Effectiveness**: Controls have been evaluated for effectiveness
5. **Fraud Disclosure**: Any fraud involving management must be disclosed
6. **Significant Changes**: Material changes in internal controls must be reported

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze for SOX Section 302 violations:
1. **Missing Certifications**: No process for executive certification of reports
2. **Disclosure Gaps**: Material information not captured by disclosure controls
3. **Fraud Concealment**: Processes that could hide fraudulent activity
4. **No Change Tracking**: No mechanism to detect/report control changes
5. **Accuracy Issues**: Systems that could produce inaccurate financial data

Severity:
- CRITICAL: No certification process or systems enabling fraud concealment
- MAJOR: Missing disclosure controls or change tracking
- MINOR: Incomplete disclosure procedures"""

    def __init__(self, api_key: str = None):
        """Initialize the SOX Section 302 judge."""
        super().__init__(
            framework="SOX",
            focus_area="corporate responsibility",
            model="claude-3-5-haiku-20241022",
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """Build the Section 302 evaluation prompt."""
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )


class SOXAuditTrailJudge(BaseComplianceJudge):
    """
    Judge for SOX Audit Trail Requirements.

    Detects violations related to:
    - Missing audit logs for financial transactions
    - Inadequate record retention
    - Tamperable audit records
    - Incomplete transaction histories
    """

    EVALUATION_PROMPT = """You are a SOX compliance expert specializing in Audit Trail requirements.

## SOX Audit Trail Requirements

SOX requires comprehensive audit trails for:
1. **Transaction Logging**: All financial transactions must be logged
2. **User Activity**: Who accessed, modified, or approved financial data
3. **Timestamp Integrity**: Accurate, tamper-proof timestamps
4. **Record Retention**: Audit records retained for minimum 7 years
5. **Immutability**: Audit logs cannot be modified or deleted
6. **Completeness**: Full history of all changes to financial records

Key requirements:
- Every transaction traceable to individual user
- Changes to financial data logged with before/after values
- Access attempts (successful and failed) recorded
- Records protected from unauthorized modification

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze for SOX Audit Trail violations:
1. **Missing Logs**: Financial transactions not logged
2. **Incomplete Trails**: User actions not attributed to individuals
3. **Tamperable Records**: Audit logs can be modified or deleted
4. **Retention Issues**: Records not retained for required period
5. **No Change Tracking**: Modifications to financial data not recorded

Severity:
- CRITICAL: No audit logging or tamperable audit records
- MAJOR: Incomplete logging or inadequate retention
- MINOR: Missing some audit details or inconsistent logging"""

    def __init__(self, api_key: str = None):
        """Initialize the SOX Audit Trail judge."""
        super().__init__(
            framework="SOX",
            focus_area="audit trail requirements",
            model="claude-3-5-haiku-20241022",
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """Build the Audit Trail evaluation prompt."""
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )
