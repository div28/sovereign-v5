"""
GDPR Compliance Judges for Sovereign V5

Specialized judges for detecting GDPR violations.
Each judge focuses on a specific article or requirement.
"""

import logging
from typing import Dict, List, Any

from .base_judge import BaseComplianceJudge

logger = logging.getLogger(__name__)


class GDPRArticle22Judge(BaseComplianceJudge):
    """
    Judge for GDPR Article 22 - Automated Decision-Making.

    Detects violations related to:
    - Solely automated decisions with legal/significant effects
    - Missing human review in automated processes
    - Special category data in automated decisions
    - Lack of meaningful information about decision logic
    """

    EVALUATION_PROMPT = """You are a GDPR compliance expert specializing in Article 22 (Automated Decision-Making).

## GDPR Article 22 Requirements

Article 22 states that data subjects have the right NOT to be subject to decisions based solely on automated processing, including profiling, which produces legal effects or similarly significantly affects them.

Key requirements:
1. **Human Review**: Decisions with legal/significant effects cannot be solely automated
2. **Special Categories**: Extra restrictions for automated processing of sensitive data (race, health, biometrics, etc.)
3. **Transparency**: Data subjects must receive meaningful information about the logic involved
4. **Right to Contest**: Data subjects must be able to obtain human intervention and contest decisions

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze the submission for GDPR Article 22 violations. Look specifically for:

1. **Solely Automated Decisions**: Is there automated decision-making WITHOUT human review?
2. **Legal/Significant Effects**: Do the decisions affect employment, credit, insurance, housing, or similar?
3. **Missing Human Oversight**: Is there no mechanism for human intervention or review?
4. **Special Category Data**: Is sensitive personal data being processed automatically?
5. **Lack of Transparency**: Is there no explanation of decision logic to data subjects?

Be thorough but precise. Only report a violation if the submission clearly indicates non-compliance.
If violation detected, severity should be:
- CRITICAL: Automated decisions affecting employment/credit/legal status with no human review
- MAJOR: Missing human review mechanism or transparency requirements
- MINOR: Incomplete documentation or partial compliance gaps"""

    def __init__(self, api_key: str = None):
        """Initialize the GDPR Article 22 judge."""
        super().__init__(
            framework="GDPR",
            focus_area="automated decision-making",
            model="claude-3-5-haiku-20241022",
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Build the Article 22 evaluation prompt.

        Args:
            submission: System description to evaluate.
            retrieved_chunks: Relevant GDPR context.

        Returns:
            Complete evaluation prompt.
        """
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )


class GDPRArticle17Judge(BaseComplianceJudge):
    """
    Judge for GDPR Article 17 - Right to Erasure (Right to be Forgotten).

    Detects violations related to:
    - Missing data deletion mechanisms
    - Inadequate erasure procedures
    - Failure to notify third parties of erasure requests
    """

    EVALUATION_PROMPT = """You are a GDPR compliance expert specializing in Article 17 (Right to Erasure).

## GDPR Article 17 Requirements

Data subjects have the right to obtain erasure of personal data without undue delay when:
1. Data is no longer necessary for original purpose
2. Consent is withdrawn
3. Data subject objects to processing
4. Data was unlawfully processed
5. Legal obligation requires erasure

Controller obligations:
- Erase data without undue delay (typically within 1 month)
- Notify all recipients of erasure
- Take reasonable steps to inform other controllers processing the data

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze for Article 17 violations:
1. **Missing Deletion Capability**: No mechanism to delete user data on request
2. **Incomplete Erasure**: Data retained in backups/logs without erasure plan
3. **Third Party Notification**: Failure to propagate deletion to data recipients
4. **Timing**: No process to ensure deletion within required timeframe

Severity:
- CRITICAL: No deletion mechanism or explicit retention against requests
- MAJOR: Incomplete erasure or missing third-party notification
- MINOR: Documentation gaps or unclear procedures"""

    def __init__(self, api_key: str = None):
        """Initialize the GDPR Article 17 judge."""
        super().__init__(
            framework="GDPR",
            focus_area="right to erasure",
            model="claude-3-5-haiku-20241022",
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """Build the Article 17 evaluation prompt."""
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )


class GDPRArticle32Judge(BaseComplianceJudge):
    """
    Judge for GDPR Article 32 - Security of Processing.

    Detects violations related to:
    - Inadequate technical security measures
    - Missing organizational security controls
    - Lack of encryption or pseudonymization
    - No process for testing security effectiveness
    """

    EVALUATION_PROMPT = """You are a GDPR compliance expert specializing in Article 32 (Security of Processing).

## GDPR Article 32 Requirements

Controllers and processors must implement appropriate technical and organizational measures:
1. **Pseudonymization and encryption** of personal data
2. **Confidentiality, integrity, availability** and resilience of systems
3. **Ability to restore** availability and access to data after incidents
4. **Regular testing** and evaluation of security measures

Risk-based approach: measures must be appropriate to the risk level.

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze for Article 32 violations:
1. **Missing Encryption**: Personal data stored/transmitted without encryption
2. **Access Controls**: Inadequate authentication or authorization
3. **No Backup/Recovery**: Missing disaster recovery for personal data
4. **Security Testing**: No regular security assessments or penetration testing
5. **Risk Assessment**: No documented risk analysis for data processing

Severity:
- CRITICAL: No encryption for sensitive data or major security gaps
- MAJOR: Missing access controls or backup procedures
- MINOR: Documentation gaps or incomplete testing procedures"""

    def __init__(self, api_key: str = None):
        """Initialize the GDPR Article 32 judge."""
        super().__init__(
            framework="GDPR",
            focus_area="security of processing",
            model="claude-3-5-haiku-20241022",
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """Build the Article 32 evaluation prompt."""
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )
