# BookCatalog Dev Server
# Starts both the FastAPI backend and React frontend dev server.
# Usage: .\scripts\Start-DevServer.ps1
#        .\scripts\Start-DevServer.ps1 -Stop

param(
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$pidFile = Join-Path $root ".dev-pids"

function Stop-DevServers {
    if (Test-Path $pidFile) {
        $savedPids = Get-Content $pidFile
        foreach ($procId in $savedPids) {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Stopping process $procId ($($proc.ProcessName))..."
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item $pidFile -Force
        Write-Host "Dev servers stopped."
    } else {
        Write-Host "No dev servers running (no .dev-pids file found)."
    }
}

if ($Stop) {
    Stop-DevServers
    return
}

# Stop any existing servers first
Stop-DevServers

Write-Host "Starting BookCatalog dev servers..." -ForegroundColor Cyan
Write-Host ""

# Start FastAPI backend
Write-Host "[Backend]  Starting FastAPI on http://localhost:8000" -ForegroundColor Green
$backend = Start-Process pwsh `
    -ArgumentList "-NoProfile", "-Command", "uv run uvicorn bookcatalog.api.main:app --port 8000 --reload" `
    -WorkingDirectory $root `
    -PassThru `
    -WindowStyle Minimized

# Start React frontend dev server
Write-Host "[Frontend] Starting Vite on http://localhost:5173" -ForegroundColor Green
$frontend = Start-Process pwsh `
    -ArgumentList "-NoProfile", "-Command", "npm run dev" `
    -WorkingDirectory (Join-Path $root "frontend") `
    -PassThru `
    -WindowStyle Minimized

# Save PIDs for clean shutdown
@($backend.Id, $frontend.Id) | Set-Content $pidFile

Write-Host ""
Write-Host "Dev servers running:" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000  (PID $($backend.Id))"
Write-Host "  Frontend: http://localhost:5173  (PID $($frontend.Id))"
Write-Host "  API docs: http://localhost:8000/docs"
Write-Host ""
Write-Host "To stop: .\scripts\Start-DevServer.ps1 -Stop" -ForegroundColor Yellow
