#!/usr/bin/env bash
# One-time setup for macOS/Linux. Usage (from repo root): bash scripts/setup.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Backend: creating venv and installing dependencies"
cd "$root/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

echo "== Frontend: installing npm dependencies"
cd "$root/frontend"
npm install

if [ ! -f "$root/.env" ]; then
  cp "$root/.env.example" "$root/.env"
  echo "== Created .env from .env.example (edit it to add API keys)"
fi

echo "== Done. Start everything with: bash scripts/dev.sh"
