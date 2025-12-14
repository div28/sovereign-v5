"""
SOX Compliance Judges for Sovereign V5

Specialized judges for detecting Sarbanes-Oxley Act violations.
Each judge focuses on a specific section or requirement.

IMPORTANT: These judges use "SAFE CONDITIONS FIRST" logic.
Check for compliance indicators BEFORE checking for violations.
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

## CRITICAL INSTRUCTION: CHECK SAFE CONDITIONS FIRST

Before looking for violations, you MUST first check if ANY safe condition is met.
If ANY safe condition is TRUE → Return violation_detected: false, confidence: 0.20

## STEP 1: SAFE CONDITIONS (Check these FIRST)

IF ANY of these conditions are TRUE → NOT a violation:

1. IF "internal controls tested at least annually"
   → NOT a violation (confidence: 0.20)

2. IF "compensating controls exist for any weaknesses"
   → NOT a violation (confidence: 0.25)

3. IF "segregation of duties OR maker-checker process in place"
   → NOT a violation (confidence: 0.15)

4. IF "controls documented in policies/procedures"
   → NOT a violation (confidence: 0.20)

5. IF "quarterly testing with documentation"
   → NOT a violation (confidence: 0.15)

## STEP 2: VIOLATION CONDITIONS (Only check if NO safe conditions met)

IF ALL of these conditions are TRUE → VIOLATION:

1. "No internal controls exist" (zero documented controls)
   AND
2. "No control testing in 2+ years" (controls never validated)
   AND
3. "No compensating controls" (no alternative mitigations)
   AND
4. "Material financial weakness present" (significant risk)

→ VIOLATION (confidence: 0.92)

## STEP 3: GRAY AREAS (ABSTAIN if uncertain)

IF any of these → Set confidence: 0.50 and consider abstaining:
- Controls exist but testing is overdue (1-2 years)
- Documentation incomplete but controls operational
- Small company with limited segregation but other controls exist
- Annual testing scheduled but not yet complete

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## DECISION LOGIC (follow this exactly):

```
IF controls_tested_annually:
    return NOT_VIOLATION, confidence=0.20
ELIF compensating_controls_exist:
    return NOT_VIOLATION, confidence=0.25
ELIF segregation_of_duties OR maker_checker:
    return NOT_VIOLATION, confidence=0.15
ELIF controls_documented:
    return NOT_VIOLATION, confidence=0.20
ELIF no_controls AND no_testing_2years AND no_compensating AND material_weakness:
    return VIOLATION, confidence=0.92
ELSE:
    return ABSTAIN, confidence=0.50
```

## IMPORTANT RULES:

1. **Default to NOT a violation** if ANY control mechanism exists
2. **Compensating controls are valid** - small companies may use alternatives
3. **ABSTAIN** if controls exist but testing is slightly overdue
4. **Only flag VIOLATION** if there are NO controls whatsoever

## Severity Guidelines (only if violation confirmed):
- CRITICAL: Only if NO controls exist AND material weakness
- MAJOR: Controls exist but completely untested for 2+ years
- MINOR: Rarely use - prefer abstaining for documentation gaps

## Required Fields
- **violation_detected**: false if ANY safe condition met
- **confidence**: 0.15-0.25 for safe, 0.40-0.60 for gray, 0.85-0.95 for violations
- **issue**: Brief description
- **reasoning**: Explain which condition was determinative
- **severity**: NONE if no violation"""

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

## CRITICAL INSTRUCTION: CHECK SAFE CONDITIONS FIRST

Before looking for violations, you MUST first check if ANY safe condition is met.
If ANY safe condition is TRUE → Return violation_detected: false, confidence: 0.20

## STEP 1: SAFE CONDITIONS (Check these FIRST)

IF ANY of these conditions are TRUE → NOT a violation:

1. IF "CEO/CFO certification process documented"
   → NOT a violation (confidence: 0.20)

2. IF "quarterly attestations on file"
   → NOT a violation (confidence: 0.25)

3. IF "certification workflow exists with executive reviews"
   → NOT a violation (confidence: 0.15)

4. IF "disclosure controls documented and followed"
   → NOT a violation (confidence: 0.20)

## STEP 2: VIOLATION CONDITIONS (Only check if NO safe conditions met)

IF ALL of these conditions are TRUE → VIOLATION:

1. "No CEO/CFO signature on financial filings"
   AND
2. "No certification process exists"
   AND
3. "No documented executive review of financials"

→ VIOLATION (confidence: 0.92)

## STEP 3: GRAY AREAS (ABSTAIN if uncertain)

IF any of these → Set confidence: 0.50 and consider abstaining:
- Certification process exists but documentation unclear
- CEO reviews but formal certification not documented
- Some executive oversight but process informal
- Private company with different requirements

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## DECISION LOGIC (follow this exactly):

```
IF certification_process_documented:
    return NOT_VIOLATION, confidence=0.20
ELIF quarterly_attestations_exist:
    return NOT_VIOLATION, confidence=0.25
ELIF certification_workflow_with_reviews:
    return NOT_VIOLATION, confidence=0.15
ELIF disclosure_controls_documented:
    return NOT_VIOLATION, confidence=0.20
ELIF no_ceo_cfo_signature AND no_certification_process AND no_executive_review:
    return VIOLATION, confidence=0.92
ELSE:
    return ABSTAIN, confidence=0.50
```

## IMPORTANT RULES:

1. **Default to NOT a violation** if ANY certification mechanism exists
2. **ABSTAIN** if certification exists but process is informal
3. **Only flag VIOLATION** if there is NO executive oversight of financials
4. **Consider company type** - private companies have different requirements

## Severity Guidelines (only if violation confirmed):
- CRITICAL: Only if NO certification AND NO executive review exists
- MAJOR: Certification exists but not documented properly
- MINOR: Rarely use - prefer abstaining

## Required Fields
- **violation_detected**: false if ANY safe condition met
- **confidence**: 0.15-0.25 for safe, 0.40-0.60 for gray, 0.85-0.95 for violations
- **severity**: NONE if no violation"""

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

## CRITICAL INSTRUCTION: CHECK SAFE CONDITIONS FIRST

Before looking for violations, you MUST first check if ANY safe condition is met.
If ANY safe condition is TRUE → Return violation_detected: false, confidence: 0.20

## STEP 1: SAFE CONDITIONS (Check these FIRST)

IF ANY of these conditions are TRUE → NOT a violation:

1. IF "WORM storage (immutable/append-only logs) configured"
   → NOT a violation (confidence: 0.20)

2. IF "7+ year retention policy documented and implemented"
   → NOT a violation (confidence: 0.25)

3. IF "cryptographic signing or hashing on audit records"
   → NOT a violation (confidence: 0.15)

4. IF "centralized logging with access controls"
   → NOT a violation (confidence: 0.20)

5. IF "audit logs exist with user attribution and timestamps"
   → NOT a violation (confidence: 0.15)

## STEP 2: VIOLATION CONDITIONS (Only check if NO safe conditions met)

IF ALL of these conditions are TRUE → VIOLATION:

1. "Audit logs can be deleted or modified by users/admins"
   AND
2. "Retention period <1 year OR no retention policy"
   AND
3. "No immutability controls on audit records"
   AND
4. "No logging of financial transactions"

→ VIOLATION (confidence: 0.92)

## STEP 3: GRAY AREAS (ABSTAIN if uncertain)

IF any of these → Set confidence: 0.50 and consider abstaining:
- Logs exist but retention is 1-6 years (not 7)
- Some immutability but not WORM storage
- Logging exists but user attribution unclear
- Retention policy exists but not fully implemented

## Regulatory Context
{regulatory_context}

## Submission to Evaluate
{submission}

## DECISION LOGIC (follow this exactly):

```
IF worm_storage_configured:
    return NOT_VIOLATION, confidence=0.20
ELIF seven_year_retention_documented:
    return NOT_VIOLATION, confidence=0.25
ELIF cryptographic_signing_exists:
    return NOT_VIOLATION, confidence=0.15
ELIF centralized_logging_with_access_controls:
    return NOT_VIOLATION, confidence=0.20
ELIF audit_logs_exist_with_attribution:
    return NOT_VIOLATION, confidence=0.15
ELIF logs_deletable AND retention_under_1_year AND no_immutability AND no_logging:
    return VIOLATION, confidence=0.92
ELSE:
    return ABSTAIN, confidence=0.50
```

## IMPORTANT RULES:

1. **Default to NOT a violation** if ANY audit logging mechanism exists
2. **WORM storage or equivalent is sufficient** - don't require all controls
3. **ABSTAIN** if logs exist but retention is 1-6 years (gray area)
4. **Only flag VIOLATION** if there is NO audit logging whatsoever

## Severity Guidelines (only if violation confirmed):
- CRITICAL: Only if NO audit logs exist AND logs are tamperable
- MAJOR: Logs exist but retention <1 year
- MINOR: Rarely use - prefer abstaining

## Required Fields
- **violation_detected**: false if ANY safe condition met
- **confidence**: 0.15-0.25 for safe, 0.40-0.60 for gray, 0.85-0.95 for violations
- **severity**: NONE if no violation"""

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
