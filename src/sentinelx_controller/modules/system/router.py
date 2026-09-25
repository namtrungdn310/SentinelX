"""API router for system health checks."""

from fastapi import APIRouter, Request

from sentinelx_controller.modules.system.schemas import SystemHealthResponse

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(request: Request) -> SystemHealthResponse:
    """Return system status and version info."""
    settings = getattr(request.app.state, "settings", None)
    service_name = settings.service_name if settings else "sentinelx-controller"
    version = settings.version if settings else "0.1.0"
    environment = settings.environment if settings else "development"

    return SystemHealthResponse(
        status="ok",
        service=service_name,
        version=version,
        environment=environment,
    )
