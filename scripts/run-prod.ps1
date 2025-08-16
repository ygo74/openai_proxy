# Run FastAPI application in production mode

Write-Host "🚀 Starting FastAPI Application - Production Mode" -ForegroundColor Green

# Load production environment variables
$envFile = ".env.prod"
if (Test-Path $envFile) {
    Write-Host "📋 Loading environment from $envFile" -ForegroundColor Yellow
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#][^=]*?)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
} else {
    Write-Host "⚠️  Environment file $envFile not found" -ForegroundColor Red
    exit 1
}

# Start FastAPI with production settings
Write-Host "🔄 Starting uvicorn server..." -ForegroundColor Blue
poetry run uvicorn src.ygo74.fastapi_openai_rag.main:app --host 0.0.0.0 --port 8000
