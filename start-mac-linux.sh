#!/usr/bin/env bash
# JARVIS launcher for macOS and Linux.
set -e
cd "$(dirname "$0")/backend"

[ -d venv ] || { echo "Creating virtual environment..."; python3 -m venv venv; }
source venv/bin/activate

python -c "import flask" 2>/dev/null || { echo "Installing dependencies..."; pip install -r requirements.txt; }

if [ ! -f .env ]; then
    cp .env.example .env
    echo "No .env found. Created one from the template."
    echo "Open backend/.env, paste your Groq API key, then run this again."
    exit 1
fi

( cd ../frontend && python3 -m http.server 8000 >/dev/null 2>&1 ) &
FRONTEND_PID=$!
trap "kill $FRONTEND_PID 2>/dev/null" EXIT

sleep 1
(command -v open >/dev/null && open http://localhost:8000) || \
(command -v xdg-open >/dev/null && xdg-open http://localhost:8000) || true

python app.py
