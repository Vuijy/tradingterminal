#!/usr/bin/env bash
# Start backend and frontend together (Ctrl+C stops both). Usage: bash scripts/dev.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

(cd "$root/backend" && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
backend_pid=$!
(cd "$root/frontend" && npm run dev) &
frontend_pid=$!

trap 'kill $backend_pid $frontend_pid 2>/dev/null' INT TERM EXIT
echo "Backend:  http://127.0.0.1:8000/docs"
echo "Frontend: http://localhost:5173"
wait
