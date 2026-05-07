$Root = Split-Path $PSScriptRoot

# Kill anything on ports 3000 and 8000
foreach ($port in @(3000, 8000)) {
    $pids = netstat -ano | Select-String ":$port\s" | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Where-Object { $_ -match '^\d+$' } | Select-Object -Unique
    foreach ($p in $pids) {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Starting backend on http://localhost:8000..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 3

Write-Host "Starting frontend on http://localhost:3000..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npx next dev --port 3000"

Start-Sleep -Seconds 5
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "Frontend: http://localhost:3000"
Write-Host "Backend:  http://localhost:8000"
