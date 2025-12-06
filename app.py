from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="Sovereign V4 - AI Compliance Intelligence",
    version="4.0.0",
    description="Pre-deployment AI compliance scanner for GDPR, SOX, EU AI Act"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your Netlify URL later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Sovereign V4 - AI Compliance Intelligence Platform",
        "version": "4.0.0",
        "status": "operational",
        "frameworks": ["GDPR", "SOX", "EU AI Act"],
        "documentation": "/docs"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint with API key validation"""
    
    # Check if environment variables are set
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    pinecone_key = os.getenv("PINECONE_API_KEY")
    
    return {
        "status": "healthy",
        "version": "4.0.0",
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
