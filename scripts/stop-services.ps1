# Stop all services script

Write-Host "🛑 Stopping all FastAPI OpenAI RAG services..." -ForegroundColor Red

# Stop development services
Write-Host "Stopping development services..." -ForegroundColor Yellow
docker compose -f docker-compose-dev.yml down

# Stop production services
Write-Host "Stopping production services..." -ForegroundColor Yellow
docker compose -f docker-compose-backend.yml down

Write-Host "✅ All services stopped" -ForegroundColor Green
