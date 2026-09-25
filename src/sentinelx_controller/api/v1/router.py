"""Main API v1 router for SentinelX Controller."""

from fastapi import APIRouter

from sentinelx_controller.modules.system.router import router as system_router

api_v1_router = APIRouter(prefix="/api/v1")

# Add routers from each module
api_v1_router.include_router(system_router)
