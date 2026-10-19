# Run every lint/type/test check, the same set CI runs.
# Usage (from repo root):  powershell -ExecutionPolicy Bypass -File scripts\check.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\backend\.venv\Scripts\python.exe"

Push-Location "$root\backend"
Write-Host "== ruff check" -ForegroundColor Yellow;  & $py -m ruff check .
Write-Host "== ruff format" -ForegroundColor Yellow; & $py -m ruff format --check .
Write-Host "== pytest" -ForegroundColor Yellow;      & $py -m pytest
Pop-Location

Push-Location "$root\frontend"
Write-Host "== eslint" -ForegroundColor Yellow;    npm run lint
Write-Host "== tsc" -ForegroundColor Yellow;       npm run typecheck
Write-Host "== prettier" -ForegroundColor Yellow;  npm run format:check
Pop-Location

Write-Host "== All checks passed" -ForegroundColor Green
