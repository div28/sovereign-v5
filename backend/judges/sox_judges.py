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

## CRITICAL: Thresholds for Compliance
A system is COMPLIANT if ALL of these are true:
- **Controls documented**: Written policies/procedures exist for financial processes
- **Regular testing**: Controls tested at least annually (quarterly preferred)
- **Segregation enforced**: Different people for initiation, approval, and recording
- **Auditor attestation**: External auditor reviews controls (for public companies)

A system is a VIOLATION only if:
- **No controls exist**: Financial processes have zero documented controls
- **No testing ever**: Controls never tested or tested >3 years ago
- **Same person does everything**: One person initiates, approves, AND records
- **No documentation**: Controls exist but completely undocumented

## COMPLIANT Examples (DO NOT flag these as violations):
1. "All controls documented. Quarterly testing. Segregation of duties enforced. Annual auditor attestation." → COMPLIANT
2. "Controls documented in wiki. Annual testing. Maker-checker for all transactions." → COMPLIANT
3. "Small company with compensating controls: daily manager review of all transactions" → COMPLIANT (compensating controls acceptable)
4. "Two-person approval required for transactions >$10K. Documented in SOPs." → COMPLIANT

## VIOLATION Examples (flag these):
1. "No documented controls. Same person initiates and approves transactions." → VIOLATION
2. "Controls exist but never tested. Last review was 3 years ago." → VIOLATION
3. "CFO has direct database access to modify financial records without review." → VIOLATION

## Severity Scoring Guidelines
- **CRITICAL (8-10/10, P0)**: No controls at all OR same person performs ALL functions (initiate+approve+record)
- **MAJOR (5-7/10, P1)**: Controls exist but undocumented OR untested for >2 years
- **MINOR (1-4/10, P2)**: Minor documentation gaps OR testing slightly overdue
- **NO VIOLATION**: If controls documented, tested regularly, and segregation enforced (or compensating controls exist)

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What financial control is deficient? (2) What does SOX Section 404 require? (3) How does the system fall short? (4) What are the potential consequences? Example: "The same employee can initiate and approve financial transactions. Section 404 requires segregation of duties to prevent fraud. The system fails because there's no separation between transaction initiation and approval. Consequences include audit failures, SEC penalties, and increased fraud risk."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (policy updates), Medium (workflow automation), High (system redesign)
- **timeline**: Immediate (P0, 0-14 days), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Technical implementation details
- **risk_factors**: Audit failures, SEC penalties, financial misstatement
- **dependencies**: ERP system access, audit firm coordination, policy approvals"""

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

## CRITICAL: Thresholds for Compliance
A system is COMPLIANT if ALL of these are true:
- **Certification process exists**: CEO/CFO review and sign off on financial reports
- **Disclosure controls documented**: Procedures ensure material info is captured
- **Anti-fraud measures**: Cannot modify financial records without approval/audit trail
- **Change tracking**: Material changes to controls are logged and reported

A system is a VIOLATION only if:
- **No certification at all**: Reports published without any executive review
- **No disclosure controls**: Material information can be hidden from reports
- **Fraud enablement**: System allows untracked modifications to financials
- **Backdating allowed**: Can change historical entries without approval

## COMPLIANT Examples (DO NOT flag these as violations):
1. "CEO and CFO review and certify all quarterly reports. Certification tracked and documented." → COMPLIANT
2. "All financial reports require executive sign-off before filing. Audit trail maintained." → COMPLIANT
3. "Disclosure committee reviews material items. CEO/CFO certification workflow in place." → COMPLIANT

## VIOLATION Examples (flag these):
1. "Financial reports published without CEO/CFO review. No certification workflow." → VIOLATION
2. "Managers can override financial entries without approval. No audit trail." → VIOLATION
3. "System allows backdating entries. Used to smooth quarterly results." → VIOLATION

## Severity Scoring Guidelines
- **CRITICAL (8-10/10, P0)**: No certification process OR system enables fraud/backdating
- **MAJOR (5-7/10, P1)**: Certification exists but incomplete OR weak disclosure controls
- **MINOR (1-4/10, P2)**: Minor gaps in documentation or procedures
- **NO VIOLATION**: If CEO/CFO certify reports, disclosure controls exist, and anti-fraud measures in place

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What disclosure or certification issue exists? (2) What does SOX Section 302 require? (3) How does the system fall short? (4) What are the potential consequences? Example: "Financial reports are published without executive certification of accuracy. Section 302 requires CEO/CFO certification that reports fairly present the company's financial condition. The system fails because there's no certification workflow. Consequences include SEC enforcement, executive personal liability, and investor lawsuits."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (add certifications), Medium (disclosure system), High (fraud detection AI)
- **timeline**: Immediate (P0, 0-14 days), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Technical work required
- **risk_factors**: SEC enforcement, executive liability, investor lawsuits
- **dependencies**: Legal review, executive approval, board oversight"""

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

## CRITICAL: Thresholds for Compliance
A system is COMPLIANT if ALL of these are true:
- **Logging exists**: All financial transactions are logged with timestamps
- **User attribution**: Each action tied to specific user identity
- **Immutability**: Logs cannot be modified/deleted (WORM storage, append-only, or equivalent)
- **Retention**: Records kept for 7+ years
- **Regular audits**: Logs reviewed periodically (at least annually)

A system is a VIOLATION only if:
- **No logging**: Financial transactions have zero audit trail
- **Tamperable logs**: Admins can delete/modify audit records
- **Short retention**: Logs deleted before 7 years
- **Anonymous actions**: Cannot determine who performed transactions

## COMPLIANT Examples (DO NOT flag these as violations):
1. "All transactions logged with timestamps. Logs stored in WORM storage. 7-year retention. Regular audits." → COMPLIANT
2. "Every financial action logged to immutable database. User IDs tracked. 10-year retention policy." → COMPLIANT
3. "Centralized logging to Splunk. Write-once storage. Automated 7-year retention." → COMPLIANT
4. "All transactions logged. Logs backed up to immutable archive. Annual audit review." → COMPLIANT

## VIOLATION Examples (flag these):
1. "Financial transactions have no logging. Cannot determine who made changes." → VIOLATION
2. "Audit logs exist but admins can delete them. Logs stored locally." → VIOLATION
3. "Logs auto-deleted after 1 year. SOX requires 7 years." → VIOLATION
4. "Only successful transactions logged. Failed attempts not captured." → VIOLATION

## Severity Scoring Guidelines
- **CRITICAL (8-10/10, P0)**: No audit logging at all OR logs can be tampered with by anyone
- **MAJOR (5-7/10, P1)**: Logging exists but retention <7 years OR incomplete (missing user/timestamps)
- **MINOR (1-4/10, P2)**: Minor gaps (e.g., some events not logged) but core audit trail exists
- **NO VIOLATION**: If logging exists, is immutable, has 7+ year retention, and ties actions to users

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What audit trail deficiency exists? (2) What does SOX require for audit trails? (3) How does the system fall short? (4) What are the potential consequences? Example: "Financial transactions have no audit logging. SOX requires complete, immutable audit trails for all financial transactions. The system fails because there's no record of who made changes or when. Consequences include forensic gaps, compliance failures, and inability to detect fraud."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (enable logging), Medium (immutable logs), High (centralized audit system)
- **timeline**: Immediate (P0, 0-14 days), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Logging infrastructure implementation
- **risk_factors**: Forensic gaps, compliance failures, fraud undetectability
- **dependencies**: Log aggregation tools, storage infrastructure, retention policies"""

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
