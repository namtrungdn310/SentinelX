"""Tests for System Readiness API endpoint."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings


def test_get_system_readiness_connected() -> None:
    """Test that GET /api/v1/system/ready returns 200 when database is healthy."""
    settings = ControllerSettings(
        environment="testing",
        service_name="test-sentinelx-controller",
        database=DatabaseSettings(url="sqlite+aiosqlite:///:memory:"),
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/system/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert data["detail"] is None
        assert "timestamp" in data


def test_get_system_readiness_disconnected() -> None:
    """Test that GET /api/v1/system/ready returns 503 when database is down."""
    settings = ControllerSettings(
        environment="testing",
        service_name="test-sentinelx-controller",
        database=DatabaseSettings(url="sqlite+aiosqlite:///:memory:"),
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        with patch(
            "sentinelx_controller.modules.system.router.check_db_readiness",
            return_value=(False, "Connection to database timed out"),
        ):
            response = client.get("/api/v1/system/ready")
            assert response.status_code == 503

            data = response.json()
            assert data["status"] == "not_ready"
            assert data["database"] == "disconnected"
            assert data["detail"] == "Connection to database timed out"
            assert "timestamp" in data
