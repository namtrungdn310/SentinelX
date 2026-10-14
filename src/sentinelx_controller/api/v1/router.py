"""Main API v1 router for SentinelX Controller."""

from fastapi import APIRouter

from sentinelx_controller.api.v1.realtime_router import router as realtime_router
from sentinelx_controller.modules.nodes.router import router as nodes_router
from sentinelx_controller.modules.projects.router import router as projects_router
from sentinelx_controller.modules.system.router import router as system_router
from sentinelx_controller.modules.telemetry.router import router as telemetry_router

api_v1_router = APIRouter(prefix="/api/v1")

# Attach module routers to API v1
api_v1_router.include_router(system_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(nodes_router)
api_v1_router.include_router(telemetry_router)
api_v1_router.include_router(realtime_router)


