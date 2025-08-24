# Development environment startup script

Write-Host "🚀 Starting FastAPI OpenAI RAG - Development Environment" -ForegroundColor Green

# Copy dev environment file
Copy-Item ".env.dev" ".env" -Force
Write-Host "✅ Copied .env.dev to .env" -ForegroundColor Yellow

# Start development backend services
Write-Host "🐳 Starting development services (LGTM + Keycloak)..." -ForegroundColor Blue
docker compose -f docker-compose-dev.yml up -d

# Wait for services to be ready
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 15  # Augmenter le délai pour LGTM

# Check if services are healthy
$keycloakHealth = try {
    $response = Invoke-RestMethod -Uri "http://localhost:8080/health/ready" -TimeoutSec 10
    $true
} catch {
    $false
}

$grafanaHealth = try {
    $response = Invoke-RestMethod -Uri "http://localhost:3000/api/health" -TimeoutSec 10
    $true
} catch {
    $false
}

# Test OTLP endpoints
$otlpGrpcHealth = try {
    $connection = Test-NetConnection -ComputerName localhost -Port 4317 -WarningAction SilentlyContinue
    $connection.TcpTestSucceeded
} catch {
    $false
}

$otlpHttpHealth = try {
    $connection = Test-NetConnection -ComputerName localhost -Port 4318 -WarningAction SilentlyContinue
    $connection.TcpTestSucceeded
} catch {
    $false
}

if ($keycloakHealth) {
    Write-Host "✅ Keycloak is healthy" -ForegroundColor Green
} else {
    Write-Host "⚠️  Keycloak might still be starting..." -ForegroundColor Yellow
}

if ($grafanaHealth) {
    Write-Host "✅ Grafana is healthy" -ForegroundColor Green
} else {
    Write-Host "⚠️  Grafana might still be starting..." -ForegroundColor Yellow
}

if ($otlpGrpcHealth) {
    Write-Host "✅ OTLP gRPC (4317) is ready" -ForegroundColor Green
} else {
    Write-Host "⚠️  OTLP gRPC (4317) not ready" -ForegroundColor Yellow
}

if ($otlpHttpHealth) {
    Write-Host "✅ OTLP HTTP (4318) is ready" -ForegroundColor Green
} else {
    Write-Host "⚠️  OTLP HTTP (4318) not ready" -ForegroundColor Yellow
}

Write-Host "🌐 Development services URLs:" -ForegroundColor Cyan
Write-Host "  - Keycloak: http://localhost:8080 (admin/admin)"
Write-Host "  - Grafana: http://localhost:3000 (admin/admin)"
Write-Host "  - Prometheus: http://localhost:9090"
Write-Host "  - Tempo: http://localhost:3200"
Write-Host "  - Loki: http://localhost:3100"

Write-Host ""
Write-Host "🔧 To start your FastAPI application:" -ForegroundColor Green
Write-Host "poetry run python -c `"from dotenv import load_dotenv; load_dotenv('.env.dev'); import uvicorn; uvicorn.run('src.ygo74.fastapi_openai_rag.main:app', host='0.0.0.0', port=8000, reload=True, log_level='debug')`""
Write-Host ""
Write-Host "🔧 Or use the dedicated script:" -ForegroundColor Green
Write-Host ".\scripts\run-dev.ps1"
