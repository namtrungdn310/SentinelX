"""Aggregated v1 router for SentinelX Controller API."""

from fastapi import APIRouter

from sentinelx_controller.modules.system.router import router as system_router

api_v1_router = APIRouter(prefix="/api/v1")

# Mount capability module routers
api_v1_router.include_router(system_router)
