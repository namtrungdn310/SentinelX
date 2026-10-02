"""API router for system health checks."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from sentinelx_controller.infrastructure.database.session import check_db_readiness
from sentinelx_controller.modules.system.schemas import (
    SystemHealthResponse,
    SystemReadinessResponse,
)

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


@router.get(
    "/ready",
    response_model=SystemReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": SystemReadinessResponse}},
)
async def get_system_readiness() -> JSONResponse:
    """Return database connectivity and system readiness status."""
    is_ready, error_msg = await check_db_readiness()

    if is_ready:
        data = SystemReadinessResponse(
            status="ready",
            database="connected",
            detail=None,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=data.model_dump(mode="json"),
        )

    data = SystemReadinessResponse(
        status="not_ready",
        database="disconnected",
        detail=error_msg,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=data.model_dump(mode="json"),
    )

