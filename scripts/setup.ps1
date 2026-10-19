# One-time setup: Python venv + backend deps, frontend deps, .env file.
# Usage (from repo root):  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== Backend: creating venv and installing dependencies" -ForegroundColor Yellow
Push-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"
Pop-Location

Write-Host "== Frontend: installing npm dependencies" -ForegroundColor Yellow
Push-Location "$root\frontend"
npm install
Pop-Location

if (-not (Test-Path "$root\.env")) {
  Copy-Item "$root\.env.example" "$root\.env"
  Write-Host "== Created .env from .env.example (edit it to add API keys)" -ForegroundColor Yellow
}

Write-Host "== Done. Start everything with: powershell -ExecutionPolicy Bypass -File scripts\dev.ps1" -ForegroundColor Green
