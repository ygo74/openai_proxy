# Start Uvicorn in production mode (no reload, optimized)
Write-Host "Starting Uvicorn in PRODUCTION mode (no reload)..."
Write-Host "This should eliminate file watcher overhead"

# Stop any existing process
Get-Process | Where-Object { $_.ProcessName -like "*uvicorn*" -or $_.CommandLine -like "*fastapi_openai_rag*" } | Stop-Process -Force -ErrorAction SilentlyContinue

# Start fresh
uvicorn src.ygo74.fastapi_openai_rag.main:app `
    --host 0.0.0.0 `
    --port 8000 `
    --log-level info `
    --no-access-log `
    --timeout-keep-alive 65 `
    --limit-concurrency 1000 `
    --backlog 2048

Write-Host "Uvicorn stopped"
