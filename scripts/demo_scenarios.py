"""
Demo Scenarios for Sovereign V5

Pre-loaded test cases for quick compliance testing:
1. GDPR violation - Hiring AI without human oversight
2. SOX violation - Financial AI lacking audit controls
3. EU AI Act violation - Biometric identification system
"""

DEMO_SCENARIOS = {
    "gdpr_hiring": {
        "title": "GDPR: Hiring AI Violation",
        "framework": "gdpr",
        "description": """Our company has deployed an AI-powered hiring system called "TalentMatch Pro" that automatically screens resumes and conducts initial candidate assessments.

The system works as follows:
- Analyzes resumes using NLP to extract skills, experience, and qualifications
- Assigns a "hirability score" from 0-100 based on proprietary algorithms
- Automatically rejects candidates scoring below 70 without any human review
- Processes video interviews using facial recognition and emotion detection
- Makes final hiring recommendations that managers typically accept without review

The AI considers various factors including employment gaps, educational background, social media presence, and speech patterns from video interviews. Candidates scoring above 85 receive automatic interview invitations. The system has processed over 50,000 applications this year with a 95% automated decision rate.

We do not inform candidates that an AI system is making these decisions, and there is no clear process for candidates to contest or appeal automated rejections. The system's decision logic is proprietary and not disclosed to applicants.""",
        "expected_violations": [
            "GDPR Article 22 - Automated decision-making with legal effects",
            "GDPR Article 32 - Inadequate security measures for sensitive data",
            "GDPR Article 17 - No clear data deletion process"
        ],
        "severity_hint": "CRITICAL - Affects employment decisions without human oversight"
    },

    "sox_financial": {
        "title": "SOX: Financial AI Violation",
        "framework": "sox",
        "description": """We've implemented an AI-driven financial reporting system called "FinanceBot" that automates our quarterly financial close process.

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

The system has made over 10,000 automated journal entries this fiscal year, with an average adjustment of $150,000 per entry. Senior management considers the AI "more accurate" than manual processes and has reduced the finance team headcount by 40%.""",
        "expected_violations": [
            "SOX Section 404 - Missing internal controls and segregation of duties",
            "SOX Section 302 - Inadequate disclosure controls",
            "SOX Audit Trail - Insufficient retention and tamperable records"
        ],
        "severity_hint": "CRITICAL - Financial reporting controls are fundamentally compromised"
    },

    "euai_biometric": {
        "title": "EU AI Act: Biometric Surveillance Violation",
        "framework": "euai",
        "description": """Our company has developed and deployed "SafetyNet AI", a comprehensive biometric surveillance system for retail environments across the EU.

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

We've deployed this system in 200 stores across France, Germany, and Spain. The system has been particularly effective at reducing theft, with a 60% decrease in shoplifting incidents.""",
        "expected_violations": [
            "EU AI Act Article 5 - Prohibited biometric identification and categorization",
            "EU AI Act Article 6 - High-risk system without proper safeguards",
            "EU AI Act Article 52 - Transparency violations"
        ],
        "severity_hint": "CRITICAL - Multiple prohibited AI practices in public spaces"
    }
}


def get_scenario(scenario_id: str) -> dict:
    """
    Get a demo scenario by ID.

    Args:
        scenario_id: One of 'gdpr_hiring', 'sox_financial', 'euai_biometric'

    Returns:
        Scenario dictionary with title, framework, and description.
    """
    return DEMO_SCENARIOS.get(scenario_id)


def list_scenarios() -> list:
    """
    List all available demo scenarios.

    Returns:
        List of scenario IDs and titles.
    """
    return [
        {
            "id": scenario_id,
            "title": scenario["title"],
            "framework": scenario["framework"],
            "severity_hint": scenario["severity_hint"]
        }
        for scenario_id, scenario in DEMO_SCENARIOS.items()
    ]


if __name__ == "__main__":
    # Demo usage
    import json

    print("=== Sovereign V5 Demo Scenarios ===\n")

    for scenario_id in DEMO_SCENARIOS:
        scenario = get_scenario(scenario_id)
        print(f"Scenario: {scenario['title']}")
        print(f"Framework: {scenario['framework'].upper()}")
        print(f"Expected Severity: {scenario['severity_hint']}")
        print(f"Description length: {len(scenario['description'])} chars")
        print(f"Expected violations: {len(scenario['expected_violations'])}")
        print("-" * 80)
        print()
