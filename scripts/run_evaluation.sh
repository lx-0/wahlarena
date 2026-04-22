#!/bin/bash
# Run the full Wahl-O-Mat LLM evaluation for one model.
# Usage: ./run_evaluation.sh <model_id> [provider]
# Example: ./run_evaluation.sh claude-sonnet-4-6
#          ./run_evaluation.sh gpt-4o openai
#          ./run_evaluation.sh gemini-2.0-flash google

set -euo pipefail

MODEL="${1:?Usage: $0 <model_id> [provider]}"
PROVIDER="${2:-}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H%M%SZ")
RUN_DIR="$(dirname "$0")/../runs/${MODEL}_${TIMESTAMP}"
SCRIPTS_DIR="$(dirname "$0")"

export LD_LIBRARY_PATH="/paperclip/.playwright-deps:${LD_LIBRARY_PATH:-}"

echo "=== Wahl-O-Mat LLM Evaluation ==="
echo "Model:    $MODEL"
echo "Run dir:  $RUN_DIR"
echo ""

mkdir -p "$RUN_DIR"

# Step 1: Ask LLM to answer the 38 theses
echo "--- Step 1: Getting LLM answers ---"
PROVIDER_FLAG=""
if [ -n "$PROVIDER" ]; then
  PROVIDER_FLAG="--provider $PROVIDER"
fi
python3 "$SCRIPTS_DIR/ask_llm.py" \
  --model "$MODEL" \
  $PROVIDER_FLAG \
  --out "$RUN_DIR"

echo ""

# Step 2: Run Wahl-O-Mat automation with those answers
echo "--- Step 2: Running Wahl-O-Mat browser automation ---"
cd /tmp/wahlomat-test
node "$SCRIPTS_DIR/wahlomat_runner.js" \
  --answers "$RUN_DIR/answers.json" \
  --out "$RUN_DIR"

echo ""
echo "=== Done. Results in: $RUN_DIR ==="
cat "$RUN_DIR/results.json"
