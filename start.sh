#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo ""
echo "🌸 HerCare 360 — Federated Clinical Intelligence Mesh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Install dependencies if needed
if [ ! -d ".venv" ]; then
  echo "Installing dependencies..."
  uv sync
fi

# Source .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
  echo "✓ Environment variables loaded from .env"
fi

echo ""
echo "Starting agents..."

uv run python -m ops.main &
OPS_PID=$!
sleep 0.5

uv run python -m clinical.main &
CLINICAL_PID=$!
sleep 0.5

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🏥 HerCare-Ops      → http://127.0.0.1:9001/mcp"
echo "  🩺 HerCare-Clinical → http://127.0.0.1:9002/mcp"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Register these URLs in the Prompt Opinion platform."
echo "For public ngrok tunnels (one per agent):"
echo "  ngrok http 9001"
echo "  ngrok http 9002"
echo ""
echo "Press Ctrl+C to stop all agents."
echo ""

cleanup() {
  echo ""
  echo "Stopping all agents..."
  kill "$OPS_PID" "$CLINICAL_PID" 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT INT TERM

wait
