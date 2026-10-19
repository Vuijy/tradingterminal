# Start backend and frontend dev servers in two new PowerShell windows.
# Usage (from repo root):  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$root\backend'; & '.\.venv\Scripts\Activate.ps1'; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$root\frontend'; npm run dev"
)

Write-Host "Backend:  http://127.0.0.1:8000/docs"
Write-Host "Frontend: http://localhost:5173"
