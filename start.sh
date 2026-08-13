#!/bin/bash
# GitWise startup script
# Run this from the project root: ./start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         GitWise — Starting Up ⚡             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Check .env ────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "⚠️  No .env file found. Creating from .env.example..."
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo ""
  echo "❗ ACTION REQUIRED:"
  echo "   Open .env and set your GOOGLE_API_KEY"
  echo "   Get a free key at: https://aistudio.google.com/app/apikey"
  echo ""
  exit 1
fi

# ── Backend ───────────────────────────────────────
echo "🔧 Starting Backend (FastAPI + LangGraph)..."
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
  echo "   Creating virtual environment with Python 3.12..."
  python3.12 -m venv venv
  ./venv/bin/pip install -r requirements.txt -q
fi

# Load env vars
export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)

./venv/bin/uvicorn main:app --port 8001 --host 0.0.0.0 --reload &
BACKEND_PID=$!
echo "   ✅ Backend PID: $BACKEND_PID  →  http://localhost:8001"

sleep 2

# ── Frontend ──────────────────────────────────────
echo ""
echo "🎨 Starting Frontend (Next.js)..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
echo "   ✅ Frontend PID: $FRONTEND_PID  →  http://localhost:3000"

echo ""
echo "════════════════════════════════════════════════"
echo "  🚀 GitWise is running!"
echo "  📖 Open: http://localhost:3000"
echo "  🔌 API:  http://localhost:8001"
echo "════════════════════════════════════════════════"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Wait for both
wait $BACKEND_PID $FRONTEND_PID
