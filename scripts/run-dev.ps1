# Run FastAPI application in development mode

Write-Host "🚀 Starting FastAPI Application - Development Mode" -ForegroundColor Green

# Load development environment variables
$envFile = ".env.dev"
if (Test-Path $envFile) {
    Write-Host "📋 Loading environment from $envFile" -ForegroundColor Yellow
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#][^=]*?)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
            Write-Host "  Set $($matches[1]) = $($matches[2])" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "⚠️  Environment file $envFile not found" -ForegroundColor Red
    exit 1
}

# Verify key environment variables
Write-Host "🔍 Environment variables verification:" -ForegroundColor Cyan
Write-Host "  OBSERVABILITY_ENABLED = $($env:OBSERVABILITY_ENABLED)" -ForegroundColor Yellow
Write-Host "  OTEL_SERVICE_NAME = $($env:OTEL_SERVICE_NAME)" -ForegroundColor Yellow
Write-Host "  OTEL_EXPORTER_OTLP_ENDPOINT = $($env:OTEL_EXPORTER_OTLP_ENDPOINT)" -ForegroundColor Yellow

# Start FastAPI with development settings
Write-Host "🔄 Starting uvicorn server..." -ForegroundColor Blue
poetry run uvicorn src.ygo74.fastapi_openai_rag.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
