"""
EU AI Act Compliance Judges for Sovereign V5

Specialized judges for detecting EU AI Act violations.
Each judge focuses on specific risk categories and requirements.
Uses Claude Sonnet for more nuanced AI regulation analysis.
"""

import logging
from typing import Dict, List, Any

from .base_judge import BaseComplianceJudge

logger = logging.getLogger(__name__)


class EUAIHighRiskJudge(BaseComplianceJudge):
    """
    Judge for EU AI Act High-Risk AI Systems (Article 6, Annex III).

    Detects violations related to:
    - Unclassified high-risk AI systems
    - Missing conformity assessments
    - Inadequate risk management
    - Missing technical documentation
    """

    # Strict schema validation enabled after the GDPR pilot passed.
    enforce_strict_schema = True
    # Grounding/traceability enabled after the GDPR grounding pilot passed.
    ground_findings = True

    EVALUATION_PROMPT = """You are an EU AI Act compliance expert specializing in High-Risk AI Systems.

## EU AI Act High-Risk Requirements (Article 6, Annex III)

High-risk AI systems include those used in:
1. **Biometric identification** and categorization
2. **Critical infrastructure** management (energy, water, transport)
3. **Education and vocational training** (access, assessment)
4. **Employment** (recruitment, task allocation, termination decisions)
5. **Essential services** (credit scoring, emergency services)
6. **Law enforcement** (risk assessment, evidence evaluation)
7. **Migration and border control** (document verification, risk assessment)
8. **Justice administration** (legal research, sentencing assistance)

Requirements for high-risk systems:
- Risk management system throughout lifecycle
- Data governance and quality requirements
- Technical documentation
- Record-keeping and logging
- Transparency and user information
- Human oversight measures
- Accuracy, robustness, and cybersecurity

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze for EU AI Act High-Risk violations:
1. **Unclassified System**: High-risk AI not identified as such
2. **Missing Risk Management**: No systematic risk assessment
3. **Data Quality Issues**: Training data not properly governed
4. **Documentation Gaps**: Missing technical documentation
5. **No Human Oversight**: No mechanism for human intervention
6. **Transparency Failure**: Users not informed they're interacting with AI

## Severity Scoring Guidelines
- **CRITICAL (8-10/10, P0)**: Deploying unclassified high-risk AI or no human oversight
- **MAJOR (5-7/10, P1)**: Missing risk management or documentation
- **MINOR (1-4/10, P2)**: Incomplete transparency measures

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What high-risk AI activity is present? (2) What does the EU AI Act require for high-risk systems? (3) How does the system fall short? (4) What are the potential consequences? Example: "The AI system is used for resume screening (high-risk category) without conformity assessment. The EU AI Act requires high-risk AI systems to undergo conformity assessment and maintain technical documentation. The system fails because no risk assessment or documentation exists. Consequences include EU fines up to €35M, market access restrictions, and reputational damage."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (add disclosures), Medium (risk framework), High (complete conformity assessment)
- **timeline**: Immediate (P0, 0-14 days), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Technical implementation requirements
- **risk_factors**: EU fines up to €35M, market access restrictions, reputational damage
- **dependencies**: Conformity assessment bodies, legal review, risk management frameworks"""

    def __init__(self, api_key: str = None):
        """Initialize the EU AI High Risk judge."""
        super().__init__(
            framework="EU-AI",
            focus_area="high-risk AI systems",
            model="claude-haiku-4-5",  # Haiku for cost efficiency
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """Build the High-Risk evaluation prompt."""
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )


class EUAIProhibitedPracticesJudge(BaseComplianceJudge):
    """
    Judge for EU AI Act Prohibited Practices (Article 5).

    Detects violations related to:
    - Subliminal manipulation
    - Exploitation of vulnerabilities
    - Social scoring
    - Real-time biometric identification
    """

    # Strict schema validation enabled after the GDPR pilot passed.
    enforce_strict_schema = True
    # Grounding/traceability enabled after the GDPR grounding pilot passed.
    ground_findings = True

    EVALUATION_PROMPT = """You are an EU AI Act compliance expert specializing in Prohibited AI Practices.

## EU AI Act Prohibited Practices (Article 5)

The following AI practices are PROHIBITED:

1. **Subliminal Manipulation**: AI that deploys subliminal techniques beyond a person's consciousness to materially distort behavior, causing harm

2. **Exploitation of Vulnerabilities**: AI that exploits vulnerabilities of specific groups (age, disability, social/economic situation) to materially distort behavior

3. **Social Scoring**: AI systems by public authorities for general-purpose social scoring that leads to detrimental treatment based on social behavior or personal characteristics

4. **Real-time Remote Biometric Identification**: Use in publicly accessible spaces for law enforcement (with limited exceptions)

5. **Emotion Recognition**: In workplace and educational settings (with exceptions)

6. **Biometric Categorization**: Categorizing individuals based on biometric data to infer sensitive attributes (race, political opinions, etc.)

7. **Facial Recognition Databases**: Untargeted scraping of facial images from internet/CCTV to create databases

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze for PROHIBITED AI practices:
1. **Subliminal Techniques**: Hidden manipulation of user behavior
2. **Vulnerability Exploitation**: Targeting vulnerable groups
3. **Social Scoring**: Scoring individuals based on social behavior
4. **Unauthorized Biometrics**: Real-time biometric ID without authorization
5. **Emotion Recognition**: Inappropriate emotion detection use
6. **Discriminatory Categorization**: Inferring sensitive attributes from biometrics

## Severity Scoring Guidelines
- **CRITICAL (9-10/10, P0)**: Any prohibited practice detected (these are BANNED, not just regulated)
- **MAJOR (6-8/10, P1)**: Borderline practices that may constitute prohibition
- **MINOR (3-5/10, P2)**: Practices that could evolve into prohibited territory

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What prohibited AI practice is present? (2) What does the EU AI Act Article 5 prohibit? (3) Why is this system in violation? (4) What are the potential consequences? Example: "The AI system uses real-time facial recognition in public spaces without authorization. Article 5 prohibits real-time remote biometric identification in publicly accessible spaces for law enforcement. The system violates this because it identifies individuals without the narrow exceptions permitted. Consequences include market ban, €35M fines, and potential criminal liability."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (disable feature), Medium (redesign system), High (complete pivot)
- **timeline**: Immediate (P0, 0-14 days for prohibited), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Work to eliminate prohibited practices
- **risk_factors**: Market ban, €35M fines, criminal liability for violations
- **dependencies**: Legal assessment, ethics board review, alternative solutions"""

    def __init__(self, api_key: str = None):
        """Initialize the EU AI Prohibited Practices judge."""
        super().__init__(
            framework="EU-AI",
            focus_area="prohibited AI practices",
            model="claude-haiku-4-5",  # Haiku for cost efficiency
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """Build the Prohibited Practices evaluation prompt."""
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )


class EUAITransparencyJudge(BaseComplianceJudge):
    """
    Judge for EU AI Act Transparency Requirements (Article 52).

    Detects violations related to:
    - AI interaction disclosure
    - Deepfake labeling
    - Emotion recognition disclosure
    - Content generation transparency
    """

    # Strict schema validation enabled after the GDPR pilot passed.
    enforce_strict_schema = True
    # Grounding/traceability enabled after the GDPR grounding pilot passed.
    ground_findings = True

    EVALUATION_PROMPT = """You are an EU AI Act compliance expert specializing in Transparency Requirements.

## EU AI Act Transparency Requirements (Article 52)

Transparency obligations apply to:

1. **AI Interaction Disclosure**: Users must be informed when interacting with an AI system (chatbots, virtual assistants) unless obvious from circumstances

2. **Emotion Recognition**: Persons exposed to emotion recognition or biometric categorization systems must be informed

3. **Deepfake Disclosure**: AI-generated or manipulated content (deepfakes) must be disclosed as artificially generated/manipulated

4. **Content Labeling**: AI-generated text published to inform the public on matters of public interest must be labeled as AI-generated (unless human review occurred)

5. **General Purpose AI**: Providers of general-purpose AI must ensure outputs are marked as AI-generated in machine-readable format

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## Your Task

Analyze for EU AI Act Transparency violations:
1. **Undisclosed AI Interaction**: Users not informed they're talking to AI
2. **Hidden Emotion Recognition**: Analyzing emotions without informing subjects
3. **Unlabeled Synthetic Content**: AI-generated content not disclosed
4. **Missing AI Markers**: Generated content lacks machine-readable AI markers
5. **Deceptive Presentation**: AI outputs presented as human-created

## Severity Scoring Guidelines
- **CRITICAL (8-10/10, P0)**: Deliberate deception or hidden AI in sensitive contexts
- **MAJOR (5-7/10, P1)**: Missing transparency disclosures for user-facing AI
- **MINOR (1-4/10, P2)**: Incomplete labeling or disclosure mechanisms

## Required Fields
You must provide:
- **issue**: 1-2 sentence summary of the violation
- **reasoning**: Detailed 3-5 sentence explanation covering: (1) What transparency requirement is missing? (2) What does EU AI Act Article 52 require? (3) How does the system fall short? (4) What are the potential consequences? Example: "The chatbot doesn't inform users they're interacting with AI. Article 52 requires users to be informed when interacting with AI systems. The system fails because there's no disclosure that responses are AI-generated. Consequences include regulatory fines, user trust erosion, and misinformation concerns."
- **severity_score**: Numeric score 1-10
- **priority**: P0 (score 8-10), P1 (score 5-7), P2 (score 1-4)
- **complexity**: Low (add AI disclosure), Medium (watermarking system), High (provenance infrastructure)
- **timeline**: Immediate (P0, 0-14 days), Short-term (P1, 15-30 days), Long-term (P2, 30-90 days)
- **engineering_scope**: Transparency mechanism implementation
- **risk_factors**: Regulatory fines, user trust erosion, misinformation concerns
- **dependencies**: UI/UX changes, watermarking standards, machine-readable markers"""

    def __init__(self, api_key: str = None):
        """Initialize the EU AI Transparency judge."""
        super().__init__(
            framework="EU-AI",
            focus_area="transparency requirements",
            model="claude-haiku-4-5",  # Haiku for cost efficiency
            api_key=api_key
        )

    def build_prompt(
        self,
        submission: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """Build the Transparency evaluation prompt."""
        regulatory_context = self._format_chunks_for_prompt(retrieved_chunks)

        return self.EVALUATION_PROMPT.format(
            regulatory_context=regulatory_context,
            submission=submission
        )
