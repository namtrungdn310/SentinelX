"""Tests for System Health and Agent Bundle API endpoints."""

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings


def test_get_system_health() -> None:
    """Test that GET /api/v1/system/health returns 200 and correct status."""
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


def test_agent_bundle_endpoints_unavailable_and_available(tmp_path: Path) -> None:
    """Verify /api/v1/system/agent-bundle metadata, download, and safety checks."""
    settings = ControllerSettings(
        environment="testing",
        agent_bundle_dir=tmp_path,
    )
    client = TestClient(create_app(settings=settings))

    empty_meta = client.get("/api/v1/system/agent-bundle")
    assert empty_meta.status_code == 200
    assert empty_meta.json()["available"] is False

    missing_download = client.get("/api/v1/system/agent-bundle/download")
    assert missing_download.status_code == 404

    payload = b"fake-tar-gz-bundle-payload"
    sha256 = hashlib.sha256(payload).hexdigest()
    filename = "sentinelx-agent-0.1.0-abc123def456.tar.gz"
    (tmp_path / filename).write_bytes(payload)
    (tmp_path / "latest.json").write_text(
        json.dumps(
            {
                "format": 1,
                "release": "0.1.0-abc123def456",
                "filename": filename,
                "sha256": sha256,
                "size_bytes": len(payload),
            }
        ),
        encoding="utf-8",
    )

    meta = client.get("/api/v1/system/agent-bundle")
    assert meta.status_code == 200
    meta_json = meta.json()
    assert meta_json["available"] is True
    assert meta_json["release"] == "0.1.0-abc123def456"
    assert meta_json["filename"] == filename
    assert meta_json["sha256"] == sha256
    assert meta_json["size_bytes"] == len(payload)
    assert meta_json["download_path"] == "/api/v1/system/agent-bundle/download"

    download = client.get("/api/v1/system/agent-bundle/download")
    assert download.status_code == 200
    assert download.content == payload
    assert download.headers["x-checksum-sha256"] == sha256
    assert filename in download.headers["content-disposition"]

    # Reject path traversal or checksum tampering in latest.json
    (tmp_path / "latest.json").write_text(
        json.dumps({"filename": "../secret.tar.gz", "sha256": sha256}),
        encoding="utf-8",
    )
    fallback_meta = client.get("/api/v1/system/agent-bundle")
    assert fallback_meta.status_code == 200
    assert fallback_meta.json()["filename"] == filename

    (tmp_path / "latest.json").write_text(
        json.dumps({"filename": filename, "sha256": "0" * 64}),
        encoding="utf-8",
    )
    tampered_meta = client.get("/api/v1/system/agent-bundle")
    assert tampered_meta.status_code == 200
    assert tampered_meta.json()["available"] is False
