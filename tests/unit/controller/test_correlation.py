"""Tests for correlation ID middleware."""

from fastapi import APIRouter
from fastapi.testclient import TestClient

from sentinelx_common.observability.logging import get_correlation_id
from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings


def test_auto_generate_correlation_id() -> None:
    """Test that requests without correlation ID get a new UUID."""
    app = create_app(settings=ControllerSettings())
    client = TestClient(app)

    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    corr_id = response.headers["X-Correlation-ID"]
    assert len(corr_id) > 0


def test_preserve_incoming_correlation_id() -> None:
    """Test that existing correlation ID is kept in the response."""
    app = create_app(settings=ControllerSettings())
    client = TestClient(app)

    custom_id = "custom-trace-uuid-12345"
    response = client.get(
        "/api/v1/system/health",
        headers={"X-Correlation-ID": custom_id},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == custom_id


def test_correlation_id_accessible_in_context() -> None:
    """Test that endpoint handlers can access the correlation ID."""
    app = create_app(settings=ControllerSettings())
    test_router = APIRouter()

    captured_id: str | None = None

    @test_router.get("/test-context")
    def sample_endpoint() -> dict[str, str | None]:
        nonlocal captured_id
        captured_id = get_correlation_id()
        return {"correlation_id": captured_id}

    app.include_router(test_router)
    client = TestClient(app)

    sent_id = "trace-ctx-999"
    response = client.get("/test-context", headers={"X-Correlation-ID": sent_id})
    assert response.status_code == 200
    assert captured_id == sent_id
    assert response.json()["correlation_id"] == sent_id
