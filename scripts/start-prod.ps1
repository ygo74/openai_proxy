# Production environment startup script

Write-Host "🚀 Starting FastAPI OpenAI RAG - Production Environment" -ForegroundColor Green

# Copy prod environment file
Copy-Item ".env.prod" ".env" -Force
Write-Host "✅ Copied .env.prod to .env" -ForegroundColor Yellow

# Start production backend services
Write-Host "🐳 Starting production services (separate containers)..." -ForegroundColor Blue
docker compose -f docker-compose-backend.yml up -d

# Wait for services to be ready
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

Write-Host "🌐 Production services URLs:" -ForegroundColor Cyan
Write-Host "  - Keycloak: http://localhost:8080 (admin/admin)"
Write-Host "  - Grafana: http://localhost:3000 (admin/admin)"
Write-Host "  - Prometheus: http://localhost:9090"
Write-Host "  - Tempo: http://localhost:3200"
Write-Host "  - Loki: http://localhost:3100"

Write-Host ""
Write-Host "🔧 To start your FastAPI application:" -ForegroundColor Green
Write-Host "poetry run uvicorn src.ygo74.fastapi_openai_rag.main:app --host 0.0.0.0 --port 8000"
