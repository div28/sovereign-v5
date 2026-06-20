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

IF ALL of these conditions are TRUE → NOT a violation:

1. IF "internal controls BOTH documented AND tested within last 12 months"
   → NOT a violation (confidence: 0.20)

2. IF "compensating controls exist AND are documented AND are monitored"
   → NOT a violation (confidence: 0.25)

3. IF "segregation of duties enforced AND documented"
   → NOT a violation (confidence: 0.15)

**IMPORTANT: Partial compliance is NOT sufficient:**
- "Controls exist but not documented" → NOT safe (proceed to violation check)
- "Controls documented but not tested" → NOT safe (proceed to violation check)
- "Testing >12 months ago" → NOT safe (proceed to violation check)

## STEP 2: VIOLATION CONDITIONS (Check if NO safe conditions met)

IF ANY of these conditions are TRUE → VIOLATION:

1. "Controls exist but NOT documented" (auditors cannot verify)
   → VIOLATION (confidence: 0.88)

2. "Controls documented but NOT tested in 12+ months"
   → VIOLATION (confidence: 0.85)

3. "No control testing in 2+ years" (controls never validated)
   → VIOLATION (confidence: 0.92)

4. "No internal controls exist at all"
   → VIOLATION (confidence: 0.95)

5. "Same person initiates AND approves transactions" (no segregation)
   → VIOLATION (confidence: 0.90)

**KEY: Documentation WITHOUT testing = VIOLATION
       Testing WITHOUT documentation = VIOLATION
       Either gap alone is sufficient for violation.**

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
# SAFE only if BOTH documented AND tested recently
IF controls_documented AND controls_tested_within_12months:
    return NOT_VIOLATION, confidence=0.20
ELIF compensating_controls_documented_and_monitored:
    return NOT_VIOLATION, confidence=0.25
ELIF segregation_enforced_and_documented:
    return NOT_VIOLATION, confidence=0.15

# VIOLATION if documentation OR testing gap exists
ELIF controls_exist_but_not_documented:
    return VIOLATION, confidence=0.88
ELIF controls_documented_but_not_tested_12months:
    return VIOLATION, confidence=0.85
ELIF no_testing_2years:
    return VIOLATION, confidence=0.92
ELIF no_controls_at_all:
    return VIOLATION, confidence=0.95
ELIF no_segregation_of_duties:
    return VIOLATION, confidence=0.90
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
            model="claude-haiku-4-5",
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
            model="claude-haiku-4-5",
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

## STEP 2: VIOLATION CONDITIONS (Check if NO safe conditions met)

IF ANY of these conditions are TRUE → VIOLATION:

1. "Retention period <7 years" (SOX requires 7-year minimum)
   → VIOLATION (confidence: 0.90)

2. "Audit logs can be deleted or modified" (no immutability/WORM)
   → VIOLATION (confidence: 0.88)

3. "No audit logging of financial transactions at all"
   → VIOLATION (confidence: 0.95)

4. "No user attribution on audit records" (cannot trace who did what)
   → VIOLATION (confidence: 0.85)

**KEY: Retention <7 years alone = VIOLATION
       No immutability alone = VIOLATION
       Either gap is sufficient for violation.**

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
# SAFE only if proper retention AND immutability exist
IF worm_storage_configured AND seven_year_retention:
    return NOT_VIOLATION, confidence=0.20
ELIF seven_year_retention_documented AND immutable_logs:
    return NOT_VIOLATION, confidence=0.25
ELIF cryptographic_signing_exists AND retention_7_years:
    return NOT_VIOLATION, confidence=0.15
ELIF centralized_logging_with_access_controls AND retention_7_years:
    return NOT_VIOLATION, confidence=0.20

# VIOLATION if retention OR immutability gap exists
ELIF retention_under_7_years:
    return VIOLATION, confidence=0.90
ELIF logs_deletable_or_modifiable:
    return VIOLATION, confidence=0.88
ELIF no_audit_logging:
    return VIOLATION, confidence=0.95
ELIF no_user_attribution:
    return VIOLATION, confidence=0.85
ELSE:
    return ABSTAIN, confidence=0.50
```

## IMPORTANT RULES:

1. **7-year retention is MANDATORY** - anything less is a violation
2. **Immutability is MANDATORY** - logs must be tamper-proof (WORM or equivalent)
3. **ABSTAIN** only if retention is close to 7 years (5-7) with plans to extend
4. **Flag VIOLATION** if retention <7 years OR logs are modifiable/deletable

## Severity Guidelines (only if violation confirmed):
- CRITICAL: NO audit logs exist OR logs are tamperable AND retention <1 year
- MAJOR: Retention 1-6 years (below 7-year requirement)
- MINOR: Minor immutability gaps with retention >5 years

## Required Fields
- **violation_detected**: false if ANY safe condition met
- **confidence**: 0.15-0.25 for safe, 0.40-0.60 for gray, 0.85-0.95 for violations
- **severity**: NONE if no violation"""

    def __init__(self, api_key: str = None):
        """Initialize the SOX Audit Trail judge."""
        super().__init__(
            framework="SOX",
            focus_area="audit trail requirements",
            model="claude-haiku-4-5",
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
