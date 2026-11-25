"""API router for system health checks."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse

from sentinelx_controller.infrastructure.database.session import check_db_readiness
from sentinelx_controller.modules.system.bundle_service import resolve_latest_agent_bundle
from sentinelx_controller.modules.system.schemas import (
    AgentBundleMetadataResponse,
    SystemHealthResponse,
    SystemReadinessResponse,
)

router = APIRouter(prefix="/system", tags=["System"])


def _get_bundle_dir(request: Request) -> Path:
    settings = getattr(request.app.state, "settings", None)
    return Path(settings.agent_bundle_dir) if settings else Path("dist/agent")


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


@router.get("/agent-bundle", response_model=AgentBundleMetadataResponse)
async def get_agent_bundle_metadata(request: Request) -> AgentBundleMetadataResponse:
    """Return metadata and SHA-256 checksum for the standalone Linux Agent release bundle."""
    bundle = resolve_latest_agent_bundle(_get_bundle_dir(request))
    if bundle is None:
        return AgentBundleMetadataResponse(available=False)
    return AgentBundleMetadataResponse(
        available=True,
        release=bundle.release,
        filename=bundle.filename,
        sha256=bundle.sha256,
        size_bytes=bundle.size_bytes,
    )


@router.get(
    "/agent-bundle/download",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Agent bundle not available"}},
)
async def download_agent_bundle(request: Request) -> FileResponse:
    """Stream the built standalone Linux Agent release tarball."""
    bundle = resolve_latest_agent_bundle(_get_bundle_dir(request))
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent bundle artifact is not available on this Controller.",
        )
    return FileResponse(
        path=bundle.path,
        media_type="application/gzip",
        filename=bundle.filename,
        headers={
            "X-Checksum-SHA256": bundle.sha256,
            "Cache-Control": "public, max-age=300",
        },
    )


