# Stop every backend process: the uvicorn launcher/reloader AND its multiprocessing
# workers. On Windows, killing only the reloader leaves a worker alive that still holds
# an inherited copy of the listening socket and keeps serving old code.
# Usage (from repo root):  powershell -ExecutionPolicy Bypass -File scripts\stop-backend.ps1
param([int]$Port = 8000)

$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -like "python*" }
$uvicorn = $procs | Where-Object { $_.CommandLine -like "*uvicorn*app.main:app*" }
$uvicornIds = @($uvicorn | ForEach-Object { $_.ProcessId })
$alive = @{}
Get-Process | ForEach-Object { $alive[$_.Id] = $true }

$workers = $procs | Where-Object {
  $_.CommandLine -like "*multiprocessing*" -and (
    ($uvicornIds -contains $_.ParentProcessId) -or
    (-not $alive.ContainsKey($_.ParentProcessId)) -or
    ($_.CommandLine -match "parent_pid=(\d+)" -and (($uvicornIds -contains [int]$Matches[1]) -or -not $alive.ContainsKey([int]$Matches[1])))
  )
}

foreach ($p in @($uvicorn) + @($workers)) {
  if ($p) {
    Write-Host "stopping PID $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue
  }
}

Start-Sleep -Milliseconds 800
$left = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($l in $left) {
  Write-Host "port $Port still held by PID $($l.OwningProcess); stopping it"
  Stop-Process -Id $l.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
  Write-Host "port $Port is STILL busy" -ForegroundColor Red
  exit 1
}
Write-Host "backend stopped; port $Port free" -ForegroundColor Green
