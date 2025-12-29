#!/bin/bash
#
# Run All Sovereign V5 Evaluations
#
# Usage:
#   ./run_all_evals.sh           # Run all evals
#   ./run_all_evals.sh --quick   # Quick run (5 scenarios each)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================"
echo -e "${BLUE}SOVEREIGN V5 - COMPLETE EVALUATION SUITE${NC}"
echo "============================================================"
echo ""
echo "Started at: $(date)"
echo "Working dir: $SCRIPT_DIR"
echo ""

# Parse arguments
QUICK_MODE=false
if [[ "$1" == "--quick" ]]; then
    QUICK_MODE=true
    echo -e "${YELLOW}Running in QUICK mode (5 scenarios each)${NC}"
    LIMIT_ARG="--limit 5"
else
    LIMIT_ARG=""
fi

# Track results
AGENTIC_RESULT="SKIPPED"
RAG_RESULT="SKIPPED"
REFLECTION_RESULT="SKIPPED"
ARIZE_RESULT="SKIPPED"

# 1. Agentic Evals
echo ""
echo "============================================================"
echo -e "${BLUE}[1/4] AGENTIC EVALUATIONS${NC}"
echo "============================================================"

if python3 run_agentic_evals.py $LIMIT_ARG; then
    AGENTIC_RESULT="${GREEN}PASS${NC}"
else
    AGENTIC_RESULT="${RED}FAIL${NC}"
fi

# 2. RAG Relevance
echo ""
echo "============================================================"
echo -e "${BLUE}[2/4] RAG RELEVANCE EVALUATION${NC}"
echo "============================================================"

if python3 eval_rag_relevance.py $LIMIT_ARG; then
    RAG_RESULT="${GREEN}PASS${NC}"
else
    RAG_RESULT="${YELLOW}WARN${NC}"
fi

# 3. Reflection Loop
echo ""
echo "============================================================"
echo -e "${BLUE}[3/4] REFLECTION LOOP EVALUATION${NC}"
echo "============================================================"

if python3 eval_reflection_loop.py; then
    REFLECTION_RESULT="${GREEN}PASS${NC}"
else
    REFLECTION_RESULT="${YELLOW}WARN${NC}"
fi

# 4. Arize Upload
echo ""
echo "============================================================"
echo -e "${BLUE}[4/4] ARIZE UPLOAD${NC}"
echo "============================================================"

if python3 upload_to_arize.py --dry-run; then
    ARIZE_RESULT="${GREEN}READY${NC}"
else
    ARIZE_RESULT="${YELLOW}SKIP${NC}"
fi

# Summary
echo ""
echo "============================================================"
echo -e "${BLUE}EVALUATION SUMMARY${NC}"
echo "============================================================"
echo ""
echo "Completed at: $(date)"
echo ""
echo "Results:"
echo -e "  Agentic Evals:    $AGENTIC_RESULT"
echo -e "  RAG Relevance:    $RAG_RESULT"
echo -e "  Reflection Loop:  $REFLECTION_RESULT"
echo -e "  Arize Upload:     $ARIZE_RESULT"
echo ""
echo "Output files:"
echo "  - agentic_eval_results.csv"
echo "  - agentic_eval_results_metrics.json"
echo "  - rag_relevance_results.csv"
echo "  - reflection_loop_results.csv"
echo ""
echo "============================================================"

# Print key metrics if available
if [[ -f "agentic_eval_results_metrics.json" ]]; then
    echo ""
    echo "Key Metrics from Agentic Evals:"
    python3 -c "
import json
with open('agentic_eval_results_metrics.json') as f:
    m = json.load(f)
print(f\"  Accuracy:   {m['accuracy']*100:.1f}%\")
print(f\"  Precision:  {m['precision']*100:.1f}%\")
print(f\"  Recall:     {m['recall']*100:.1f}%\")
print(f\"  F1 Score:   {m['f1']*100:.1f}%\")
print(f\"  Avg Iterations: {m['avg_iterations']:.1f}\")
"
fi

echo ""
echo "Done!"
