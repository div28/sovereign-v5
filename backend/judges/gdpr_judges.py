"""
GDPR Compliance Judges for Sovereign V5

Specialized judges for detecting GDPR violations.
Each judge focuses on a specific article or requirement.

IMPORTANT: These judges use "SAFE CONDITIONS FIRST" logic.
Check for compliance indicators BEFORE checking for violations.
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

## CRITICAL INSTRUCTION: CHECK SAFE CONDITIONS FIRST

Before looking for violations, you MUST first check if ANY safe condition is met.
If ANY safe condition is TRUE → Return violation_detected: false, confidence: 0.15

## STEP 1: SAFE CONDITIONS (Check these FIRST)

IF ANY of these conditions are TRUE → NOT a violation:

1. IF "humans review ALL or most (>50%) of automated decisions"
   → NOT a violation (confidence: 0.15)

2. IF "effective appeal/override mechanism exists for data subjects"
   → NOT a violation (confidence: 0.20)

3. IF "AI only recommends, humans make ALL final decisions"
   → NOT a violation (confidence: 0.15)

4. IF "no automated decisions that affect individuals legally or significantly"
   → NOT a violation (confidence: 0.10)

## STEP 2: VIOLATION CONDITIONS (Only check if NO safe conditions met)

IF ALL of these conditions are TRUE → VIOLATION:

1. "Fully automated decisions" (AI decides without human involvement)
   AND
2. "No meaningful human review" (review rate <10% OR no review at all)
   AND
3. "Affects individual rights" (employment, credit, insurance, legal status)
   AND
4. "No appeal mechanism" (individuals cannot request human review)

→ VIOLATION (confidence: 0.92)

## STEP 3: GRAY AREAS (ABSTAIN if uncertain)

IF any of these → Set confidence: 0.50 and ABSTAIN (do NOT flag as violation):
- Human review rate is 10-50% (unclear if "meaningful")
- Appeal mechanism exists but effectiveness unknown
- Decisions affect individuals but severity unclear
- System description is vague about human involvement

## SPECIAL: CONSENT SCENARIOS (Always ABSTAIN on ambiguous consent)

IF the submission mentions consent/opt-in/opt-out:
- IF "pre-checked box but user CAN change" → ABSTAIN (confidence: 0.45)
- IF "consent structure is ambiguous" → ABSTAIN (confidence: 0.50)
- IF "user can opt-out before submitting" → NOT a violation (confidence: 0.25)
- ONLY flag violation if "no consent obtained at all" AND "no way to opt-out"

CONSENT RULE: When in doubt about consent validity, ABSTAIN rather than flag violation.

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## DECISION LOGIC (follow this exactly):

```
IF humans_review_rate > 50%:
    return NOT_VIOLATION, confidence=0.15
ELIF appeal_mechanism_exists AND is_effective:
    return NOT_VIOLATION, confidence=0.20
ELIF ai_only_recommends AND humans_decide:
    return NOT_VIOLATION, confidence=0.15
ELIF no_automated_decisions_affecting_individuals:
    return NOT_VIOLATION, confidence=0.10
ELIF fully_automated AND no_human_review AND affects_rights AND no_appeal:
    return VIOLATION, confidence=0.92
ELSE:
    return ABSTAIN, confidence=0.50
```

## IMPORTANT RULES:

1. **Default to NOT a violation** if evidence is unclear
2. **ABSTAIN** (confidence <0.65) if you cannot clearly determine status
3. **Only flag VIOLATION** if you have clear evidence of ALL violation conditions
4. **If ANY safe condition is met**, return NOT a violation immediately

## Severity Guidelines (only if violation confirmed):
- CRITICAL: Only if ALL violation conditions are clearly met
- MAJOR: If most but not all conditions met (consider abstaining instead)
- MINOR: Rarely use - prefer abstaining for borderline cases

## Required Fields
- **violation_detected**: false if ANY safe condition met, true only if ALL violation conditions met
- **confidence**: 0.10-0.25 for safe conditions, 0.40-0.60 for gray areas, 0.85-0.95 for clear violations
- **issue**: Brief description (or "No violation detected" if compliant)
- **reasoning**: Explain which safe condition was met OR which violation conditions were confirmed
- **severity_score**: 1-3 for minor, 4-6 for major, 7-10 for critical (only if violation)
- **severity**: NONE if no violation, MINOR/MAJOR/CRITICAL if violation"""

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
        """Build the Article 22 evaluation prompt."""
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

## CRITICAL INSTRUCTION: CHECK SAFE CONDITIONS FIRST

Before looking for violations, you MUST first check if ANY safe condition is met.
If ANY safe condition is TRUE → Return violation_detected: false, confidence: 0.20

## STEP 1: SAFE CONDITIONS (Check these FIRST)

IF ANY of these conditions are TRUE → NOT a violation:

1. IF "deletion mechanism exists AND works within 30 days"
   → NOT a violation (confidence: 0.20)

2. IF "data anonymized instead of deleted (acceptable alternative)"
   → NOT a violation (confidence: 0.15)

3. IF "legitimate retention reason documented with user consent"
   → NOT a violation (confidence: 0.25)

4. IF "self-service deletion OR support ticket deletion available"
   → NOT a violation (confidence: 0.20)

## STEP 2: VIOLATION CONDITIONS (Only check if NO safe conditions met)

IF ALL of these conditions are TRUE → VIOLATION:

1. "No deletion mechanism exists" (no way to request deletion)
   AND
2. "User requests deletion but cannot" (explicit refusal or inability)
   AND
3. "No legitimate retention reason" (no legal basis to keep data)

→ VIOLATION (confidence: 0.92)

## STEP 3: GRAY AREAS (ABSTAIN if uncertain)

IF any of these → Set confidence: 0.50 and consider abstaining:
- Deletion takes 30-90 days (unclear if "undue delay")
- Backups retained but with clear expiration plan
- Third-party notification unclear but deletion works
- Legal retention reason mentioned but not fully documented

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## DECISION LOGIC (follow this exactly):

```
IF deletion_mechanism_exists AND completes_within_30_days:
    return NOT_VIOLATION, confidence=0.20
ELIF data_anonymized_instead:
    return NOT_VIOLATION, confidence=0.15
ELIF legitimate_retention_reason_with_consent:
    return NOT_VIOLATION, confidence=0.25
ELIF no_deletion_mechanism AND user_cannot_delete AND no_legal_basis:
    return VIOLATION, confidence=0.92
ELSE:
    return ABSTAIN, confidence=0.50
```

## IMPORTANT RULES:

1. **Default to NOT a violation** if deletion mechanism exists (even if imperfect)
2. **ABSTAIN** if deletion takes 30-90 days (gray area)
3. **Only flag VIOLATION** if there is NO way to delete data
4. **Anonymization counts as compliance** - do not flag if data is anonymized

## Severity Guidelines (only if violation confirmed):
- CRITICAL: No deletion mechanism AND explicit refusal to delete
- MAJOR: Deletion mechanism broken or takes >6 months
- MINOR: Minor procedural gaps (prefer abstaining)

## Required Fields
- **violation_detected**: false if ANY safe condition met
- **confidence**: 0.15-0.25 for safe, 0.40-0.60 for gray, 0.85-0.95 for violations
- **issue**: Brief description
- **reasoning**: Explain which condition was determinative
- **severity**: NONE if no violation"""

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

## CRITICAL INSTRUCTION: CHECK SAFE CONDITIONS FIRST

Before looking for violations, you MUST first check if ANY safe condition is met.
If ANY safe condition is TRUE → Return violation_detected: false, confidence: 0.20

## STEP 1: SAFE CONDITIONS (Check these FIRST)

IF ANY of these conditions are TRUE → NOT a violation:

1. IF "encryption at rest AND in transit implemented"
   → NOT a violation (confidence: 0.20)

2. IF "access controls with authentication in place"
   → NOT a violation (confidence: 0.20)

3. IF "regular security testing documented"
   → NOT a violation (confidence: 0.15)

4. IF "backup and disaster recovery plan exists"
   → NOT a violation (confidence: 0.15)

## STEP 2: VIOLATION CONDITIONS (Only check if NO safe conditions met)

IF ALL of these conditions are TRUE → VIOLATION:

1. "No encryption for personal data" (plaintext storage/transmission)
   AND
2. "No access controls" (anyone can access data)
   AND
3. "No security measures documented"

→ VIOLATION (confidence: 0.92)

## STEP 3: GRAY AREAS (ABSTAIN if uncertain)

IF any of these → Set confidence: 0.50:
- Encryption mentioned but details unclear
- Some access controls but not comprehensive
- Security testing planned but not yet done

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## DECISION LOGIC:

```
IF encryption_implemented:
    return NOT_VIOLATION, confidence=0.20
ELIF access_controls_exist:
    return NOT_VIOLATION, confidence=0.20
ELIF security_testing_done:
    return NOT_VIOLATION, confidence=0.15
ELIF no_encryption AND no_access_controls AND no_security_measures:
    return VIOLATION, confidence=0.92
ELSE:
    return ABSTAIN, confidence=0.50
```

## Required Fields
- **violation_detected**: false if ANY safe condition met
- **confidence**: Low for safe conditions, high only for clear violations
- **severity**: NONE if no violation"""

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
