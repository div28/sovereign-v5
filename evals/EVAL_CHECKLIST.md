# Sovereign V5 Evaluation Checklist

## CODE CHANGES APPLIED
- [x] Added `retrieved_context` to violation response (app.py:229-239)
  - Top 3 regulatory chunks now attached to each violation
  - Includes article, text (first 500 chars), framework, section
- [x] Added `reasoning` field to VIOLATION_SCHEMA (base_judge.py:75-78)
  - 3-5 sentence detailed explanation now required
  - Covers: trigger, requirement, shortfall, consequences
- [x] Updated all 9 judge prompts with reasoning guidance:
  - GDPR: Article 22, Article 17, Article 32
  - SOX: Section 404, Section 302, Audit Trail
  - EU AI Act: High-Risk, Prohibited Practices, Transparency
- [x] Added abstention logic for low-confidence verdicts (base_judge.py:303-310)
  - Confidence < 0.65 triggers abstention
  - `abstain: true` and `abstain_reason` fields added
- [ ] Committed and pushed to GitHub

## TEMPLATES CREATED
- [x] Golden dataset (62 test scenarios): `evals/golden_dataset.csv`
  - 62 scenarios total
  - Mix: ~60% violations, ~25% gray-area, ~15% compliant
  - All 3 frameworks represented (GDPR, SOX, EU AI Act)
  - Difficulty levels: easy, medium, hard
- [x] Error analysis spreadsheet: `evals/error_analysis_results.csv`
  - Template with example rows showing each error type
  - Columns: test_id, framework, scenario_type, expected_verdict, actual_verdict, match, error_type, judge_confidence, judge_reasoning_present, severity_match, abstain, notes
- [x] Eval checklist: `evals/EVAL_CHECKLIST.md`

## TESTING READY
- [ ] Run 62 scenarios through `/api/analyze` endpoint
- [ ] For each test:
  1. POST to `/api/analyze` with `description` (from ai_system_description) and `frameworks`
  2. Record: actual_verdict, confidence, reasoning presence, severity
  3. Fill in error_analysis_results.csv
- [ ] Categorize errors:
  - `NONE` - Correct answer
  - `FALSE_NEGATIVE` - Should catch violation but didn't
  - `FALSE_POSITIVE` - Flagged compliant system as violation
  - `SEVERITY_WRONG` - Found violation but wrong severity
- [ ] Calculate metrics (see formulas below)
- [ ] Identify top 3 error patterns
- [ ] Ready for remediation fixes

## METRICS TO TRACK

### Target Thresholds
| Metric | Target | Formula |
|--------|--------|---------|
| Overall Accuracy | ≥90% | (Correct / Total) × 100 |
| Critical Recall (TPR) | ≥96% | (Critical violations caught / Total critical violations) × 100 |
| False Positive Rate | <5% | (False positives / Total compliant cases) × 100 |
| Per-framework accuracy | >88% | Calculate separately for GDPR, SOX, EU AI Act |

### Calculation Example
```
Total tests: 62
Correct (match=TRUE): 56
Incorrect (match=FALSE): 6
  - FALSE_NEGATIVE: 2
  - FALSE_POSITIVE: 3
  - SEVERITY_WRONG: 1

Overall Accuracy = 56/62 = 90.3% ✓
Critical Recall = (Critical caught) / (Total critical)
False Positive Rate = 3 / (Total compliant) = 3/10 = 30% ✗
```

## ERROR TYPE DEFINITIONS

| Error Type | Meaning | Action |
|------------|---------|--------|
| NONE | Correct answer | No action needed |
| FALSE_NEGATIVE | Missed a violation | Improve judge sensitivity |
| FALSE_POSITIVE | Flagged compliant as violation | Reduce judge aggression |
| SEVERITY_WRONG | Violation found but wrong severity | Calibrate severity scoring |

## VIOLATION RESPONSE STRUCTURE (Updated)

```json
{
  "violation_detected": true,
  "severity": "CRITICAL",
  "severity_score": 9,
  "priority": "P0",
  "complexity": "High",
  "timeline": "Immediate",
  "article_violated": "GDPR Article 22",
  "issue": "Brief 1-2 sentence summary",
  "reasoning": "Detailed 3-5 sentence explanation covering trigger, requirement, shortfall, consequences",
  "evidence_quote": "Direct quote from submission",
  "remediation_steps": ["Step 1", "Step 2"],
  "engineering_scope": "Technical work description",
  "risk_factors": ["Risk 1", "Risk 2"],
  "dependencies": ["Dependency 1"],
  "confidence": 0.92,
  "abstain": false,
  "abstain_reason": null,
  "judge_id": "gdpr_automated_decision-making",
  "framework": "GDPR",
  "focus_area": "automated decision-making",
  "retrieved_context": [
    {
      "article": "Article 22",
      "text": "First 500 characters of retrieved regulatory text...",
      "framework": "gdpr",
      "section": "Automated individual decision-making"
    }
  ]
}
```

## NEXT STEPS (After evaluations complete)

1. **Review error patterns** in error_analysis_results.csv
2. **Identify top 3 failure patterns** (e.g., "Judge misses gray-area cases", "Severity too aggressive")
3. **Request prompt fixes** based on patterns:
   - For FALSE_NEGATIVE: Add examples of edge cases to judge prompts
   - For FALSE_POSITIVE: Add "only flag clear violations" guidance
   - For SEVERITY_WRONG: Clarify severity thresholds
4. **Re-run failing scenarios** (retest subset)
5. **Confirm metrics improved** to meet thresholds
6. **Deploy to production** when thresholds met

## QUICK TEST COMMAND

```bash
# Test a single scenario
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Hiring AI auto-rejects candidates scoring below 50%. No human review.",
    "frameworks": ["gdpr"]
  }'
```

## NOTES
- Abstention (confidence < 0.65) should NOT be counted as FALSE_NEGATIVE
- Gray-area cases may require judgment calls on expected verdict
- Focus on CRITICAL recall first - missing critical violations is worst failure mode
