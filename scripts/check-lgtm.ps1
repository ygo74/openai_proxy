# Check LGTM container status and endpoints

Write-Host "🔍 LGTM Container Diagnostic" -ForegroundColor Green

# Check if LGTM container is running
$lgtmContainer = docker ps --filter "name=lgtm" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
if ($lgtmContainer) {
    Write-Host "📦 LGTM Container Status:" -ForegroundColor Yellow
    Write-Host $lgtmContainer
} else {
    Write-Host "❌ LGTM container not found" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Check container logs for errors
Write-Host "📋 Recent LGTM logs (last 20 lines):" -ForegroundColor Blue
docker logs --tail 20 fastapi-openai-rag-lgtm-1

Write-Host ""

# Test LGTM endpoints
$endpoints = @{
    "Grafana" = "http://localhost:3000/api/health"
    "Prometheus" = "http://localhost:9090/-/healthy"
    "Loki" = "http://localhost:3100/ready"
    "Tempo" = "http://localhost:3200/ready"
}

Write-Host "🌐 Testing LGTM endpoints:" -ForegroundColor Cyan
foreach ($service in $endpoints.Keys) {
    $url = $endpoints[$service]
    try {
        $response = Invoke-RestMethod -Uri $url -TimeoutSec 5
        Write-Host "  ✅ $service - OK" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ $service - FAILED ($($_.Exception.Message))" -ForegroundColor Red
    }
}

Write-Host ""

# Test OTLP ports
$otlpPorts = @{
    "OTLP gRPC" = 4317
    "OTLP HTTP" = 4318
}

Write-Host "🔌 Testing OTLP ports:" -ForegroundColor Cyan
foreach ($service in $otlpPorts.Keys) {
    $port = $otlpPorts[$service]
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
Write-Host "💡 Troubleshooting tips:" -ForegroundColor Yellow
Write-Host "  - Restart LGTM: docker compose -f docker-compose-dev.yml restart lgtm"
Write-Host "  - Check full logs: docker logs -f fastapi-openai-rag-lgtm-1"
Write-Host "  - Reset everything: docker compose -f docker-compose-dev.yml down && docker compose -f docker-compose-dev.yml up -d"
