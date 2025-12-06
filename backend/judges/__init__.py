"""Compliance Judges for Sovereign V5."""

from .base_judge import BaseComplianceJudge, Severity, VIOLATION_SCHEMA
from .gdpr_judges import GDPRArticle22Judge, GDPRArticle17Judge, GDPRArticle32Judge
from .sox_judges import SOXSection404Judge, SOXSection302Judge, SOXAuditTrailJudge
from .euai_judges import EUAIHighRiskJudge, EUAIProhibitedPracticesJudge, EUAITransparencyJudge

__all__ = [
    # Base
    "BaseComplianceJudge",
    "Severity",
    "VIOLATION_SCHEMA",
    # GDPR Judges
    "GDPRArticle22Judge",
    "GDPRArticle17Judge",
    "GDPRArticle32Judge",
    # SOX Judges
    "SOXSection404Judge",
    "SOXSection302Judge",
    "SOXAuditTrailJudge",
    # EU AI Act Judges
    "EUAIHighRiskJudge",
    "EUAIProhibitedPracticesJudge",
    "EUAITransparencyJudge",
]
