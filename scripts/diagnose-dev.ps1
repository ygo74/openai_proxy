# Development environment diagnostic script

Write-Host "🔍 FastAPI OpenAI RAG - Development Diagnostic" -ForegroundColor Green

# Check if development services are running
Write-Host "🐳 Checking Docker services..." -ForegroundColor Blue

$containers = docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Where-Object { $_ -match "keycloak|lgtm" }
if ($containers) {
    Write-Host "Running containers:" -ForegroundColor Yellow
    $containers | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "❌ No development containers running" -ForegroundColor Red
    Write-Host "Run: docker compose -f docker-compose-dev.yml up -d" -ForegroundColor Yellow
}

Write-Host ""

# Check port connectivity
Write-Host "🌐 Testing port connectivity..." -ForegroundColor Blue

$ports = @{
    "Keycloak" = 8080
    "Grafana" = 3000
    "Prometheus" = 9090
    "Loki" = 3100
    "Tempo" = 3200
    "OTLP gRPC" = 4317
    "OTLP HTTP" = 4318
}

foreach ($service in $ports.Keys) {
    $port = $ports[$service]
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue
        if ($connection.TcpTestSucceeded) {
            Write-Host "  ✅ $service (port $port) - OK" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $service (port $port) - NOT REACHABLE" -ForegroundColor Red
        }
    } catch {
        Write-Host "  ❌ $service (port $port) - ERROR: $_" -ForegroundColor Red
    }
}

Write-Host ""

# Check environment configuration
Write-Host "📋 Checking environment configuration..." -ForegroundColor Blue

if (Test-Path ".env") {
    $env_content = Get-Content ".env"
    $otel_endpoint = ($env_content | Where-Object { $_ -match "OTEL_EXPORTER_OTLP_ENDPOINT=" }) -replace "OTEL_EXPORTER_OTLP_ENDPOINT=", ""
    $otel_enabled = ($env_content | Where-Object { $_ -match "OBSERVABILITY_ENABLED=" }) -replace "OBSERVABILITY_ENABLED=", ""

    Write-Host "  OTLP Endpoint: $otel_endpoint" -ForegroundColor Yellow
    Write-Host "  Observability Enabled: $otel_enabled" -ForegroundColor Yellow

    if ($otel_endpoint -match "4317") {
        Write-Host "  ✅ Using OTLP gRPC (4317)" -ForegroundColor Green
    } elseif ($otel_endpoint -match "4318") {
        Write-Host "  ✅ Using OTLP HTTP (4318)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Unknown OTLP endpoint format" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ .env file not found" -ForegroundColor Red
}

Write-Host ""

# Test FastAPI app if running
Write-Host "🚀 Testing FastAPI application..." -ForegroundColor Blue

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3
    Write-Host "  ✅ FastAPI app is running" -ForegroundColor Green

    # Test OpenTelemetry status
    try {
        $otel_status = Invoke-RestMethod -Uri "http://localhost:8000/otel/status" -TimeoutSec 3
        Write-Host "  📊 OpenTelemetry Status:" -ForegroundColor Cyan
        Write-Host "    - Service initialized: $($otel_status.telemetry_service.initialized)" -ForegroundColor Yellow
        Write-Host "    - Observability enabled: $($otel_status.telemetry_service.settings.enabled)" -ForegroundColor Yellow
        Write-Host "    - OTLP endpoint reachable: $($otel_status.connectivity.otlp_endpoint.reachable)" -ForegroundColor $(if ($otel_status.connectivity.otlp_endpoint.reachable) { "Green" } else { "Red" })
    } catch {
        Write-Host "  ⚠️  Could not check OpenTelemetry status: $_" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ FastAPI app not running on port 8000" -ForegroundColor Red
    Write-Host "  Start with: .\scripts\run-dev.ps1" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🔧 Quick fixes:" -ForegroundColor Cyan
Write-Host "  - Start services: docker compose -f docker-compose-dev.yml up -d" -ForegroundColor White
Write-Host "  - Restart services: docker compose -f docker-compose-dev.yml restart" -ForegroundColor White
Write-Host "  - Check logs: docker compose -f docker-compose-dev.yml logs lgtm" -ForegroundColor White
Write-Host "  - Reset environment: .\scripts\start-dev.ps1" -ForegroundColor White
