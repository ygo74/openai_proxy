"""Rate limit management endpoints.

DEPRECATED: These endpoints were designed for the old TokenRateLimitService.
The new RateLimitService uses a database-backed system with admin API endpoints.
See interfaces/api/admin/rate_limits.py for the new rate limit management endpoints.

TODO: Rewrite these endpoints to work with the new RateLimitService if needed.
The old methods like get_rate_limit_info() and get_current_usage() don't exist anymore.
The new system uses scope-based rate limits (global/model/group_model) stored in database.

For now, this file just exports an empty router to prevent import errors.
"""
from fastapi import APIRouter

# Export empty router to maintain compatibility with existing route registration
router = APIRouter()

# All user-facing rate limit query endpoints have been removed.
# Rate limit management is now done via the admin API in:
# src/ygo74/fastapi_openai_rag/interfaces/api/admin/rate_limits.py
#
# The new admin endpoints provide:
# - GET /admin/rate-limits - List all rate limit configurations
# - POST /admin/rate-limits/models/{model_id} - Create/update model-specific limits
# - POST /admin/rate-limits/groups/{group_name}/models/{model_id} - Create/update group/model limits
# - POST /admin/rate-limits/global - Create/update global limits
# - DELETE /admin/rate-limits/{scope_type}/{scope_id} - Delete rate limit configuration
#
# Rate limit enforcement happens automatically in ChatCompletionService._check_rate_limits()
# Users don't need to query their limits - they'll receive 429 errors when exceeded.
