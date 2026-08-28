"""Unit tests for System Health API endpoint."""

from fastapi.testclient import TestClient

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings


def test_get_system_health() -> None:
    """Test GET /api/v1/system/health returns 200 OK and valid health payload."""
    settings = ControllerSettings(
        environment="testing",
        service_name="test-sentinelx-controller",
        version="0.1.0",
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get("/api/v1/system/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "test-sentinelx-controller"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "testing"
    assert "timestamp" in data
