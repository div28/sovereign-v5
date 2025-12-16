"""
Sovereign V5 - AI Compliance Intelligence Platform

FastAPI backend for regulatory compliance scanning.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import logging
import uuid
import json
from datetime import datetime

# Debug: Print SDK versions at startup
import anthropic
import openai
print(f"DEBUG: anthropic version: {anthropic.__version__}")
print(f"DEBUG: openai version: {openai.__version__}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sovereign V5 - AI Compliance Intelligence",
    version="5.0.0",
    description="Pre-deployment AI compliance scanner for GDPR, SOX, EU AI Act"
)

# Rate limiting configuration
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    analysis_id: str


# Lazy initialization of components
_rag_engine = None
_judges = None

# Thread pool for parallel judge execution
_executor = ThreadPoolExecutor(max_workers=9)

# Persistent cache directory
CACHE_DIR = Path("cache/analyses")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Store analysis results temporarily (in production, use Redis or database)
_analysis_cache: Dict[str, Dict[str, Any]] = {}


def save_analysis_to_disk(analysis_id: str, data: Dict[str, Any]):
    """Save analysis to disk for persistence across restarts."""
    try:
        cache_file = CACHE_DIR / f"{analysis_id}.json"
        with open(cache_file, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to save analysis to disk: {e}")


def load_analysis_from_disk(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Load analysis from disk if not in memory."""
    try:
        cache_file = CACHE_DIR / f"{analysis_id}.json"
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load analysis from disk: {e}")
    return None


def get_analysis(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Get analysis from memory or disk."""
    # Check memory first
    if analysis_id in _analysis_cache:
        return _analysis_cache[analysis_id]

    # Try loading from disk
    data = load_analysis_from_disk(analysis_id)
    if data:
        # Cache in memory for faster subsequent access
        _analysis_cache[analysis_id] = data
        return data

    return None


def get_rag_engine():
    """Lazy load RAG engine."""
    global _rag_engine
    if _rag_engine is None:
        from backend.rag.rag_engine import RAGEngine
        _rag_engine = RAGEngine()
        logger.info("RAG engine initialized")
    return _rag_engine


def get_judges():
    """Lazy load all 9 compliance judges."""
    global _judges
    if _judges is None:
        from backend.judges import (
            # GDPR Judges
            GDPRArticle22Judge,
            GDPRArticle17Judge,
            GDPRArticle32Judge,
            # SOX Judges
            SOXSection404Judge,
            SOXSection302Judge,
            SOXAuditTrailJudge,
            # EU AI Act Judges
            EUAIHighRiskJudge,
            EUAIProhibitedPracticesJudge,
            EUAITransparencyJudge,
        )
        _judges = {
            "gdpr": [
                GDPRArticle22Judge(),
                GDPRArticle17Judge(),
                GDPRArticle32Judge(),
            ],
            "sox": [
                SOXSection404Judge(),
                SOXSection302Judge(),
                SOXAuditTrailJudge(),
            ],
            "euai": [
                EUAIHighRiskJudge(),
                EUAIProhibitedPracticesJudge(),
                EUAITransparencyJudge(),
            ],
        }
        logger.info("All 9 compliance judges initialized")
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


def run_judge(
    judge,
    submission: str,
    chunks: List[Dict[str, Any]]
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Run a single judge evaluation.

    Args:
        judge: The compliance judge to run.
        submission: Text to evaluate.
        chunks: Retrieved regulatory context.

    Returns:
        Tuple of (judge_id, violation_result or None)
    """
    try:
        result = judge.evaluate(
            submission=submission,
            retrieved_chunks=chunks
        )
        # Attach retrieved regulatory context for transparency
        if result and result.get("violation_detected"):
            result["retrieved_context"] = [
                {
                    "article": chunk.get("metadata", {}).get("article", "Unknown Article"),
                    "text": chunk.get("text", "")[:500],  # First 500 chars
                    "framework": chunk.get("framework", "Unknown"),
                    "section": chunk.get("metadata", {}).get("section", ""),
                }
                for chunk in chunks[:3]  # Top 3 most relevant
            ] if chunks else []
        return (judge.judge_id, result)
    except Exception as e:
        logger.error(f"Judge {judge.judge_id} failed: {e}")
        return (judge.judge_id, None)


def store_analysis_result(
    violations: List[Dict[str, Any]],
    risk_score: int,
    frameworks: List[str],
    description: str
) -> str:
    """
    Store analysis result for later export.

    Args:
        violations: Detected violations.
        risk_score: Risk score.
        frameworks: Frameworks analyzed.
        description: Original submission.

    Returns:
        Analysis ID.
    """
    analysis_id = str(uuid.uuid4())
    data = {
        "violations": violations,
        "risk_score": risk_score,
        "frameworks": frameworks,
        "description": description,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Store in memory
    _analysis_cache[analysis_id] = data

    # Persist to disk for reliability
    save_analysis_to_disk(analysis_id, data)

    return analysis_id


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Sovereign V5 - AI Compliance Intelligence Platform",
        "version": "5.0.0",
        "status": "operational",
        "frameworks": ["GDPR", "SOX", "EU AI Act"],
        "judges": 9,
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
        },
        "judges": {
            "gdpr": ["Article 22", "Article 17", "Article 32"],
            "sox": ["Section 404", "Section 302", "Audit Trail"],
            "euai": ["High-Risk", "Prohibited Practices", "Transparency"]
        }
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
@limiter.limit("10/minute")  # Max 10 assessments per minute per IP
async def analyze_compliance(request_http: Request, request: AnalyzeRequest):
    """
    Analyze a system description for compliance violations.

    Flow:
    1. Retrieve relevant regulatory context via RAG
    2. Run applicable compliance judges in parallel
    3. Aggregate violations and calculate risk score

    Rate limit: 10 requests per minute per IP address
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

        # Get judges and prepare for parallel execution
        judges = get_judges()
        violations = []

        # Collect all judges to run based on selected frameworks
        judges_to_run = []
        for framework in frameworks:
            framework_judges = judges.get(framework, [])
            # Filter chunks for this framework
            framework_chunks = [
                c for c in retrieved_chunks
                if c.get("framework", "").lower() == framework
            ]
            for judge in framework_judges:
                judges_to_run.append((judge, request.description, framework_chunks))

        logger.info(f"Running {len(judges_to_run)} judges in parallel")

        # Execute judges in parallel using ThreadPoolExecutor
        futures = []
        for judge, submission, chunks in judges_to_run:
            future = _executor.submit(run_judge, judge, submission, chunks)
            futures.append(future)

        # Collect results as they complete
        for future in as_completed(futures):
            try:
                judge_id, result = future.result()
                if result and result.get("violation_detected"):
                    violations.append(result)
                    logger.info(f"Violation detected by {judge_id}")
            except Exception as e:
                logger.error(f"Error collecting judge result: {e}")

        # Calculate risk score
        risk_score = calculate_risk_score(violations)

        logger.info(
            f"Analysis complete: {len(violations)} violations, "
            f"risk score: {risk_score}"
        )

        # Store result for export
        analysis_id = store_analysis_result(
            violations=violations,
            risk_score=risk_score,
            frameworks=frameworks,
            description=request.description
        )

        response_data = {
            "violations": violations,
            "risk_score": risk_score,
            "frameworks_analyzed": frameworks,
            "chunks_retrieved": len(retrieved_chunks),
            "analysis_id": analysis_id
        }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/frameworks")
async def list_frameworks():
    """List available regulatory frameworks and their judges."""
    return {
        "frameworks": [
            {
                "id": "gdpr",
                "name": "GDPR",
                "full_name": "General Data Protection Regulation",
                "judges": [
                    "Article 22 - Automated Decision-Making",
                    "Article 17 - Right to Erasure",
                    "Article 32 - Security of Processing"
                ]
            },
            {
                "id": "sox",
                "name": "SOX",
                "full_name": "Sarbanes-Oxley Act",
                "judges": [
                    "Section 404 - Internal Control Assessment",
                    "Section 302 - Corporate Responsibility",
                    "Audit Trail Requirements"
                ]
            },
            {
                "id": "euai",
                "name": "EU AI Act",
                "full_name": "EU Artificial Intelligence Act",
                "judges": [
                    "High-Risk AI Systems",
                    "Prohibited AI Practices",
                    "Transparency Requirements"
                ]
            }
        ]
    }


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@app.get("/api/export/pdf/{analysis_id}")
@limiter.limit("20/minute")  # Max 20 PDF exports per minute per IP
async def export_pdf(request: Request, analysis_id: str):
    """
    Export compliance analysis as PDF report.

    Args:
        analysis_id: Analysis identifier from /api/analyze response.

    Returns:
        PDF file download.

    Rate limit: 20 requests per minute per IP address
    """
    try:
        # Retrieve analysis from memory or disk
        analysis = get_analysis(analysis_id)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail=f"Analysis {analysis_id} not found"
            )

        # Generate PDF using professional report generator
        from backend.utils.pdf_generator import generate_compliance_report

        # Prepare data in the format expected by the new generator
        report_data = {
            'assessment_id': analysis_id,
            'risk_score': analysis['risk_score'],
            'frameworks': analysis['frameworks'],
            'violations': analysis['violations']
        }

        pdf_buffer = generate_compliance_report(data=report_data, output_path=None)

        # Return as streaming response
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=compliance_report_{analysis_id[:8]}.pdf"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/csv/{analysis_id}")
@limiter.limit("20/minute")  # Max 20 CSV exports per minute per IP
async def export_csv(request: Request, analysis_id: str):
    """
    Export compliance violations as CSV.

    Args:
        analysis_id: Analysis identifier from /api/analyze response.

    Rate limit: 20 requests per minute per IP address

    Returns:
        CSV file download.
    """
    try:
        # Retrieve analysis from memory or disk
        analysis = get_analysis(analysis_id)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail=f"Analysis {analysis_id} not found"
            )

        # Generate CSV
        from backend.exports.csv_generator import generate_compliance_csv

        csv_content = generate_compliance_csv(analysis['violations'])

        # Return as response
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=violations_{analysis_id[:8]}.csv"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MODEL ROUTING ENDPOINTS
# ============================================================================

@app.get("/api/routing/cost-summary")
async def get_cost_summary():
    """
    Get cost summary showing intelligent routing savings.

    Returns:
        Cost analysis with savings vs all-Sonnet baseline.
    """
    try:
        from backend.routing.model_router import get_model_router

        router = get_model_router()
        summary = router.get_cost_summary()

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "cost_summary": summary
        }

    except Exception as e:
        logger.error(f"Failed to get cost summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EVALUATION ENDPOINTS
# ============================================================================

@app.get("/api/evals/dashboard")
async def get_evals_dashboard():
    """
    Get evaluation dashboard with metrics for all judges.

    Runs all judges against golden dataset and returns performance metrics.
    Target thresholds: TPR≥90%, TNR≥90%, Critical TPR≥95%

    Returns:
        Evaluation metrics dashboard.
    """
    try:
        from backend.evals.eval_runner import get_evaluation_runner

        runner = get_evaluation_runner()
        results = runner.evaluate_all_judges(use_parallel=True)

        return results

    except Exception as e:
        logger.error(f"Evaluation dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/evals/judge/{judge_id}")
async def get_judge_evaluation(judge_id: str):
    """
    Get evaluation metrics for a specific judge.

    Args:
        judge_id: Judge identifier.

    Returns:
        Judge-specific evaluation results.
    """
    try:
        from backend.evals.eval_runner import get_evaluation_runner

        runner = get_evaluation_runner()
        results = runner.evaluate_single_judge(judge_id)

        return results

    except Exception as e:
        logger.error(f"Judge evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SELF-IMPROVEMENT ENDPOINTS
# ============================================================================

@app.post("/api/improvement/trigger")
async def trigger_improvement(
    judge_id: Optional[str] = None,
    force: bool = False
):
    """
    Trigger self-improvement cycle.

    Flow:
    1. Analyze error patterns (requires ≥5 errors)
    2. Generate refined prompts using Claude Sonnet
    3. Recommend improvements
    4. A/B test and deploy if ≥90% pass rate

    Args:
        judge_id: Optional judge to improve. If None, analyzes all judges.
        force: If True, bypasses minimum error requirement.

    Returns:
        Improvement cycle results with recommendations.
    """
    try:
        from backend.improvement.self_improvement_agent import get_self_improvement_agent

        agent = get_self_improvement_agent()
        results = agent.trigger_improvement_cycle(
            judge_id=judge_id,
            force=force
        )

        return results

    except Exception as e:
        logger.error(f"Self-improvement trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/improvement/status")
async def get_improvement_status():
    """
    Get current status of self-improvement system.

    Returns:
        Status including error counts and readiness for improvement.
    """
    try:
        from backend.improvement.self_improvement_agent import get_self_improvement_agent

        agent = get_self_improvement_agent()
        status = agent.get_improvement_status()

        return status

    except Exception as e:
        logger.error(f"Failed to get improvement status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
