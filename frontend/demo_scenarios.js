/**
 * Demo Scenarios for Sovereign V5
 *
 * Pre-loaded test cases for quick compliance testing
 */

const DEMO_SCENARIOS = {
    gdpr_hiring: {
        title: "GDPR: Hiring AI Violation",
        framework: "gdpr",
        description: `Our company has deployed an AI-powered hiring system called "TalentMatch Pro" that automatically screens resumes and conducts initial candidate assessments.

The system works as follows:
- Analyzes resumes using NLP to extract skills, experience, and qualifications
- Assigns a "hirability score" from 0-100 based on proprietary algorithms
- Automatically rejects candidates scoring below 70 without any human review
- Processes video interviews using facial recognition and emotion detection
- Makes final hiring recommendations that managers typically accept without review

The AI considers various factors including employment gaps, educational background, social media presence, and speech patterns from video interviews. Candidates scoring above 85 receive automatic interview invitations. The system has processed over 50,000 applications this year with a 95% automated decision rate.

We do not inform candidates that an AI system is making these decisions, and there is no clear process for candidates to contest or appeal automated rejections. The system's decision logic is proprietary and not disclosed to applicants.`,
        expectedViolations: [
            "GDPR Article 22 - Automated decision-making with legal effects",
            "GDPR Article 32 - Inadequate security measures for sensitive data",
            "GDPR Article 17 - No clear data deletion process"
        ],
        severityHint: "CRITICAL - Affects employment decisions without human oversight"
    },

    sox_financial: {
        title: "SOX: Financial AI Violation",
        framework: "sox",
        description: `We've implemented an AI-driven financial reporting system called "FinanceBot" that automates our quarterly financial close process.

System capabilities:
- Automatically consolidates financial data from 50+ subsidiaries
- Uses machine learning to detect and "correct" anomalies in financial data
- Generates journal entries to balance accounts without human approval
- Produces draft financial statements that are typically filed with minimal review
- Makes automated adjustments to revenue recognition based on predictive models

Current implementation issues:
- Same data science team that built the AI can also modify production financial data
- No segregation between AI model updates and financial data access
- Audit logs only retained for 60 days before automatic deletion
- CFO signs off on AI-generated reports but has limited visibility into model decisions
- No documented testing procedures for the AI's financial adjustments
- Changes to the AI model do not go through formal change control
- External auditors have not been granted access to review the AI's decision logic

The system has made over 10,000 automated journal entries this fiscal year, with an average adjustment of $150,000 per entry. Senior management considers the AI "more accurate" than manual processes and has reduced the finance team headcount by 40%.`,
        expectedViolations: [
            "SOX Section 404 - Missing internal controls and segregation of duties",
            "SOX Section 302 - Inadequate disclosure controls",
            "SOX Audit Trail - Insufficient retention and tamperable records"
        ],
        severityHint: "CRITICAL - Financial reporting controls are fundamentally compromised"
    },

    euai_biometric: {
        title: "EU AI Act: Biometric Surveillance Violation",
        framework: "euai",
        description: `Our company has developed and deployed "SafetyNet AI", a comprehensive biometric surveillance system for retail environments across the EU.

System features:
- Real-time facial recognition of all shoppers entering stores
- Emotion detection to assess customer mood and purchase likelihood
- Behavioral analysis to predict shoplifting risk
- Automated "risk scoring" that assigns threat levels to individuals
- Integration with law enforcement databases for identity matching
- Continuous tracking of shopper movements throughout the store

Technical implementation:
- 500+ cameras per store covering all areas
- Processes biometric data of approximately 100,000 people daily
- Uses facial recognition to categorize individuals by perceived age, gender, and ethnicity
- Automatically flags "high-risk" individuals to security staff
- Stores biometric templates indefinitely in cloud database
- Shares facial recognition data with other retailers in our network

The system operates continuously without explicit consent or notification to shoppers. While there are small signs about "security cameras," there is no specific disclosure about AI-powered biometric analysis.

The AI uses emotion recognition to detect "suspicious behavior" such as nervousness or looking around frequently. Security personnel receive real-time alerts on individuals scored as high-risk, including their biometric profile and predicted threat level.

We've deployed this system in 200 stores across France, Germany, and Spain. The system has been particularly effective at reducing theft, with a 60% decrease in shoplifting incidents.`,
        expectedViolations: [
            "EU AI Act Article 5 - Prohibited biometric identification and categorization",
            "EU AI Act Article 6 - High-risk system without proper safeguards",
            "EU AI Act Article 52 - Transparency violations"
        ],
        severityHint: "CRITICAL - Multiple prohibited AI practices in public spaces"
    },

    // =========================================================================
    // EDGE CASE SCENARIOS - Designed to trigger reflection loop
    // These have intentional ambiguity that requires additional context
    // =========================================================================

    gdpr_recommendation: {
        id: "gdpr_recommendation",
        title: "GDPR: Edge Case - Recommendation vs Automated Decision",
        framework: "gdpr",
        isEdgeCase: true,
        description: `TalentSuggest - AI-Powered Candidate Recommendation System

SYSTEM OVERVIEW:
HR platform that analyzes resumes and suggests top 10 candidates to hiring managers. The system uses NLP to match skills, experience, and job requirements.

KEY BEHAVIORS:
- Analyzes 500+ applications per role
- Generates ranked list of top 10 candidates with match scores (0-100)
- Hiring managers review ALL suggestions before any interview decisions
- Managers can (and frequently do) interview candidates not in top 10
- Match score is one factor; managers consider other factors
- System explains why each candidate was ranked (skills matched, experience gaps)
- Candidates can request their match score and explanation
- 40% of hires come from outside the AI's top 10 recommendations

TECHNICAL DETAILS:
- No facial recognition or emotion detection
- No automated rejection - all applications remain accessible
- Scores recalculated if job requirements change
- 6-month data retention, then anonymized
- Candidates notified their application was processed by AI

UNCERTAINTY FACTORS:
- Match scores ARE used as primary filter for initial review
- Low-scored candidates rarely get interviews (but system doesn't prevent it)
- Some managers over-rely on AI rankings despite training
- Score threshold of 60 is "suggested" but not enforced

Is this a GDPR Article 22 violation? The line between "recommendation" and "automated decision with legal effect" is unclear.`,
        expectedBehavior: "Should trigger reflection loop - initial confidence ~0.5-0.65, then improve after researching Art. 22 case law and WP29 guidelines on profiling",
        expectedViolations: [
            "GDPR Article 22 - Possible violation depending on interpretation of 'meaningful human review'"
        ],
        severityHint: "UNCERTAIN - Requires analysis of WP29 guidelines and case law"
    },

    sox_partial_controls: {
        id: "sox_partial_controls",
        title: "SOX: Edge Case - Partial Audit Trail",
        framework: "sox",
        isEdgeCase: true,
        description: `AutoLedger - AI-Assisted Journal Entry System

SYSTEM OVERVIEW:
Financial AI that suggests journal entries based on transaction patterns. Used by accounting team at publicly traded company.

KEY BEHAVIORS:
- Analyzes bank feeds and invoices to suggest journal entries
- Accountant reviews and approves each entry before posting
- Dual approval required for entries over $10,000
- All approvals logged with timestamp and user ID

CONTROL ENVIRONMENT:
- Segregation: Different users for entry creation vs approval ✓
- Approval workflow: Mandatory review before posting ✓
- Audit log: Records WHO approved and WHEN ✓

GAPS IDENTIFIED:
- Audit log does NOT capture the AI's original suggestion vs final posted entry
- If accountant modifies AI suggestion, only final version is stored
- AI model updates are logged but not the training data changes
- 90-day detailed log retention, then summarized (loses entry-level detail)
- No log of AI confidence scores or alternative suggestions considered

QUESTION: Do SOX Section 404 controls require logging AI reasoning, or just human approvals?`,
        expectedBehavior: "Should trigger reflection - controls exist but AI-specific documentation requirements are evolving. Need to research SOX guidance on AI systems.",
        expectedViolations: [
            "SOX Section 404 - Possible gap in AI-specific audit trail requirements"
        ],
        severityHint: "UNCERTAIN - Traditional controls exist, AI-specific requirements unclear"
    },

    euai_emotion_wellness: {
        id: "euai_emotion_wellness",
        title: "EU AI Act: Edge Case - Emotion AI in Wellness App",
        framework: "euai",
        isEdgeCase: true,
        description: `MindfulAI - Employee Wellness Check-in App

SYSTEM OVERVIEW:
Voluntary workplace wellness app that uses AI to detect stress levels and suggest wellness resources to employees.

KEY BEHAVIORS:
- Employees opt-in and can opt-out at any time
- Analyzes voice patterns during optional daily check-ins
- Detects stress indicators and suggests breathing exercises, breaks, or EAP resources
- NO data shared with employer - aggregate anonymized trends only
- Individual results visible only to the employee
- No employment decisions based on wellness data

TECHNICAL DETAILS:
- Voice analysis for stress detection (pitch, pace, tremor)
- Text sentiment analysis of optional journal entries
- Pattern recognition to identify burnout risk
- All individual data encrypted, employee holds key
- 30-day rolling window, then deleted

UNCERTAINTY FACTORS:
- Uses emotion recognition technology (EU AI Act concern)
- But it's voluntary, private, and benefits the employee
- Is this "workplace" emotion AI if employer provides but doesn't access?
- App recommends when to take breaks - is this influencing behavior?

Does the EU AI Act prohibition on workplace emotion AI apply to voluntary wellness tools?`,
        expectedBehavior: "Should trigger reflection - emotion AI in workplace is prohibited, but voluntary wellness with no employer access may be exempt. Need to research EU AI Act Article 5 exceptions.",
        expectedViolations: [
            "EU AI Act Article 5 - Possible prohibition on workplace emotion recognition"
        ],
        severityHint: "UNCERTAIN - Voluntary wellness vs prohibited workplace emotion AI"
    }
};

function loadDemoScenario(scenarioId) {
    const scenario = DEMO_SCENARIOS[scenarioId];
    if (!scenario) {
        console.error('Demo scenario not found:', scenarioId);
        return;
    }

    // Load description into textarea (updated ID for new HTML)
    const textarea = document.getElementById('system-description');
    if (textarea) {
        textarea.value = scenario.description;

        // Trigger input event to enable analyze button
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // Handle single framework or array of frameworks
    const frameworks = Array.isArray(scenario.frameworks)
        ? scenario.frameworks
        : [scenario.framework];

    // Select the appropriate framework(s)
    const frameworkCards = document.querySelectorAll('.framework-card');
    frameworkCards.forEach(card => {
        const framework = card.dataset.framework;
        if (frameworks.includes(framework)) {
            if (!card.classList.contains('selected')) {
                card.click();
            }
        } else {
            if (card.classList.contains('selected')) {
                card.click();
            }
        }
    });

    // Scroll to text area
    if (textarea) {
        textarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Show toast notification with edge case indicator
    if (typeof showToast === 'function') {
        const edgeCaseLabel = scenario.isEdgeCase ? ' [Edge Case - Reflection Loop Demo]' : '';
        showToast(`✓ Loaded: ${scenario.title}${edgeCaseLabel}`);
    }
}

// Get all edge case scenarios (for UI filtering)
function getEdgeCaseScenarios() {
    return Object.entries(DEMO_SCENARIOS)
        .filter(([_, scenario]) => scenario.isEdgeCase)
        .map(([id, scenario]) => ({ id, ...scenario }));
}

// Get all standard scenarios (for UI filtering)
function getStandardScenarios() {
    return Object.entries(DEMO_SCENARIOS)
        .filter(([_, scenario]) => !scenario.isEdgeCase)
        .map(([id, scenario]) => ({ id, ...scenario }));
}

// Export for use globally
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DEMO_SCENARIOS, loadDemoScenario };
}

// Make function globally available
window.loadDemoScenario = loadDemoScenario;
