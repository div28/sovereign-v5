"""
Sovereign V5 - AI Compliance Intelligence Platform

FastAPI backend for regulatory compliance scanning.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sovereign V5 - AI Compliance Intelligence",
    version="5.0.0",
    description="Pre-deployment AI compliance scanner for GDPR, SOX, EU AI Act"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Request/Response Models
class AnalyzeRequest(BaseModel):
    """Request model for compliance analysis."""
    description: str
    frameworks: List[str]


class ViolationResponse(BaseModel):
    """Individual violation in response."""
    violation_detected: bool
    severity: str
    article_violated: str
    evidence_quote: str
    remediation_steps: List[str]
    confidence: float
    judge_id: str
    framework: str
    focus_area: str


class AnalyzeResponse(BaseModel):
    """Response model for compliance analysis."""
    violations: List[Dict[str, Any]]
    risk_score: int
    frameworks_analyzed: List[str]
    chunks_retrieved: int


# Lazy initialization of components
_rag_engine = None
_judges = None


def get_rag_engine():
    """Lazy load RAG engine."""
    global _rag_engine
    if _rag_engine is None:
        from backend.rag.rag_engine import RAGEngine
        _rag_engine = RAGEngine()
        logger.info("RAG engine initialized")
    return _rag_engine


def get_judges():
    """Lazy load compliance judges."""
    global _judges
    if _judges is None:
        from backend.judges import GDPRArticle22Judge, GDPRArticle17Judge, GDPRArticle32Judge
        _judges = {
            "gdpr": [
                GDPRArticle22Judge(),
                GDPRArticle17Judge(),
                GDPRArticle32Judge(),
            ]
        }
        logger.info("Compliance judges initialized")
    return _judges


def calculate_risk_score(violations: List[Dict[str, Any]]) -> int:
    """
    Calculate overall risk score from violations.

    Returns score from 0-100 where:
    - 0-25: Low risk
    - 26-50: Medium risk
    - 51-75: High risk
    - 76-100: Critical risk
    """
    if not violations:
        return 0

    severity_weights = {
        "CRITICAL": 40,
        "MAJOR": 25,
        "MINOR": 10,
        "NONE": 0
    }

    total_score = 0
    for violation in violations:
        severity = violation.get("severity", "NONE")
        confidence = violation.get("confidence", 0.5)
        weight = severity_weights.get(severity, 0)
        total_score += weight * confidence

    # Cap at 100
    return min(int(total_score), 100)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Sovereign V5 - AI Compliance Intelligence Platform",
        "version": "5.0.0",
        "status": "operational",
        "frameworks": ["GDPR", "SOX", "EU AI Act"],
        "documentation": "/docs"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint with API key validation."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    pinecone_key = os.getenv("PINECONE_API_KEY")

    return {
        "status": "healthy",
        "version": "5.0.0",
        "api_keys": {
            "anthropic": "configured" if anthropic_key else "missing",
            "openai": "configured" if openai_key else "missing",
            "pinecone": "configured" if pinecone_key else "missing"
        },
        "pinecone_indexes": {
            "gdpr": "sovereign-gdpr-regulation",
            "sox": "sovereign-sox-regulation",
            "euai": "sovereign-euai-regulation"
        }
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_compliance(request: AnalyzeRequest):
    """
    Analyze a system description for compliance violations.

    Flow:
    1. Retrieve relevant regulatory context via RAG
    2. Run applicable compliance judges
    3. Aggregate violations and calculate risk score
    """
    try:
        # Validate request
        if not request.description or not request.description.strip():
            raise HTTPException(status_code=400, detail="Description is required")

        if not request.frameworks:
            raise HTTPException(status_code=400, detail="At least one framework is required")

        # Normalize frameworks
        frameworks = [f.lower() for f in request.frameworks]
        valid_frameworks = ["gdpr", "sox", "euai"]
        frameworks = [f for f in frameworks if f in valid_frameworks]

        if not frameworks:
            raise HTTPException(
                status_code=400,
                detail=f"No valid frameworks. Choose from: {valid_frameworks}"
            )

        logger.info(f"Analyzing submission for frameworks: {frameworks}")

        # Get RAG engine and retrieve context
        rag = get_rag_engine()
        retrieved_chunks = rag.retrieve_for_evaluation(
            submission_text=request.description,
            frameworks=frameworks,
            top_k=15
        )

        logger.info(f"Retrieved {len(retrieved_chunks)} chunks")

        # Get judges and evaluate
        judges = get_judges()
        violations = []

        for framework in frameworks:
            framework_judges = judges.get(framework, [])
            for judge in framework_judges:
                try:
                    # Filter chunks for this framework
                    framework_chunks = [
                        c for c in retrieved_chunks
                        if c.get("framework", "").lower() == framework
                    ]

                    result = judge.evaluate(
                        submission=request.description,
                        retrieved_chunks=framework_chunks
                    )

                    if result and result.get("violation_detected"):
                        violations.append(result)

                except Exception as e:
                    logger.error(f"Judge {judge.judge_id} failed: {e}")
                    continue

        # Calculate risk score
        risk_score = calculate_risk_score(violations)

        logger.info(
            f"Analysis complete: {len(violations)} violations, "
            f"risk score: {risk_score}"
        )

        return AnalyzeResponse(
            violations=violations,
            risk_score=risk_score,
            frameworks_analyzed=frameworks,
            chunks_retrieved=len(retrieved_chunks)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/frameworks")
async def list_frameworks():
    """List available regulatory frameworks."""
    return {
        "frameworks": [
            {
                "id": "gdpr",
                "name": "GDPR",
                "full_name": "General Data Protection Regulation",
                "judges": ["Article 22 - Automated Decision-Making",
                          "Article 17 - Right to Erasure",
                          "Article 32 - Security of Processing"]
            },
            {
                "id": "sox",
                "name": "SOX",
                "full_name": "Sarbanes-Oxley Act",
                "judges": ["Coming soon"]
            },
            {
                "id": "euai",
                "name": "EU AI Act",
                "full_name": "EU Artificial Intelligence Act",
                "judges": ["Coming soon"]
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
