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

## Severity Scoring Guidelines
- **CRITICAL (8-10/10, P0)**: Automated decisions affecting employment/credit/legal status with no human review
- **MAJOR (5-7/10, P1)**: Missing human review mechanism or transparency requirements
- **MINOR (1-4/10, P2)**: Incomplete documentation or partial compliance gaps

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What activity in the AI system triggers this article? (2) What does GDPR Article 22 require? (3) How does the system fall short? (4) What are the potential consequences? Example: "The AI system automatically rejects candidates scoring below 50% without allowing appeals. Article 22(1) requires individuals have the right NOT to be subject to automated decisions affecting them significantly. The system fails this because there is no meaningful human review option. Consequences include regulatory fines up to €20M or 4% of annual turnover and legal liability."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (config changes), Medium (feature additions), High (architectural changes)
- **timeline**: Immediate (P0, 0-14 days), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Detailed technical work description
- **risk_factors**: Legal, regulatory, reputational risks
- **dependencies**: Prerequisites like vendor integrations, data migrations, etc."""

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

## Severity Scoring Guidelines
- **CRITICAL (8-10/10, P0)**: No deletion mechanism or explicit retention against requests
- **MAJOR (5-7/10, P1)**: Incomplete erasure or missing third-party notification
- **MINOR (1-4/10, P2)**: Documentation gaps or unclear procedures

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What data handling practice triggers this article? (2) What does GDPR Article 17 require? (3) How does the system fall short? (4) What are the potential consequences? Example: "The system stores user data indefinitely with no deletion mechanism. Article 17 grants users the right to erasure of personal data without undue delay. The system fails because users cannot request deletion. Consequences include GDPR fines up to €20M and loss of user trust."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (add delete endpoint), Medium (cascade deletions), High (data lake cleanup)
- **timeline**: Immediate (P0, 0-14 days), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Technical implementation details
- **risk_factors**: GDPR fines, user trust issues, regulatory scrutiny
- **dependencies**: Database access, third-party API integrations, backup systems"""

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

## Severity Scoring Guidelines
- **CRITICAL (8-10/10, P0)**: No encryption for sensitive data or major security gaps
- **MAJOR (5-7/10, P1)**: Missing access controls or backup procedures
- **MINOR (1-4/10, P2)**: Documentation gaps or incomplete testing procedures

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What security practice is deficient? (2) What does GDPR Article 32 require? (3) How does the system fall short? (4) What are the potential consequences? Example: "Personal data is stored unencrypted in the database. Article 32 requires appropriate technical measures including encryption. The system fails because sensitive data is exposed if the database is breached. Consequences include data breaches, GDPR fines, and reputational damage."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (enable TLS), Medium (implement encryption), High (zero-trust architecture)
- **timeline**: Immediate (P0, 0-14 days), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Security measures to implement
- **risk_factors**: Data breaches, GDPR fines, security incidents
- **dependencies**: Key management systems, security tools, compliance frameworks"""

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
