"""Tests for SentinelX Pydantic wire contracts."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from sentinelx_common.contracts import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    MetricBatchRequest,
    MetricBatchResponse,
    MetricSample,
    NodeRegisterRequest,
    NodeResponse,
    NodeStatus,
    ProjectCreateRequest,
    ProjectResponse,
)


def test_project_create_request_valid() -> None:
    """Test creating a valid ProjectCreateRequest."""
    req = ProjectCreateRequest(name="Project Alpha", description="Test project")
    assert req.name == "Project Alpha"
    assert req.description == "Test project"


def test_project_create_request_invalid_name() -> None:
    """Test that empty name or name too long raises ValidationError."""
    with pytest.raises(ValidationError):
        ProjectCreateRequest(name="")

    with pytest.raises(ValidationError):
        ProjectCreateRequest(name="a" * 101)


def test_project_forbids_extra_fields() -> None:
    """Test that extra unexpected fields are rejected by SentinelXBaseModel."""
    with pytest.raises(ValidationError):
        ProjectCreateRequest(name="Valid Name", unknown_field="unexpected")  # type: ignore[call-arg]


def test_project_response_valid() -> None:
    """Test ProjectResponse with valid UUID and datetime."""
    now = datetime.now(UTC)
    resp = ProjectResponse(
        project_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        name="Project Alpha",
        created_at=now,
    )
    assert resp.project_id == "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
    assert resp.created_at == now


def test_node_register_request_valid() -> None:
    """Test NodeRegisterRequest with valid IP and hostname."""
    req = NodeRegisterRequest(
        project_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        hostname="server-01",
        ip_address="192.168.1.100",
        os_info="Ubuntu 22.04 LTS",
    )
    assert req.hostname == "server-01"
    assert req.ip_address == "192.168.1.100"


def test_node_register_request_invalid_ip() -> None:
    """Test that invalid short IP address raises ValidationError."""
    with pytest.raises(ValidationError):
        NodeRegisterRequest(
            project_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
            hostname="server-01",
            ip_address="1.1",  # Too short (min_length=7)
        )


def test_node_response_status() -> None:
    """Test NodeResponse status defaults to UNENROLLED."""
    now = datetime.now(UTC)
    resp = NodeResponse(
        node_id="11111111-2222-3333-4444-555555555555",
        project_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        hostname="server-01",
        ip_address="10.0.0.1",
        created_at=now,
    )
    assert resp.status == NodeStatus.UNENROLLED
    assert resp.last_seen is None


def test_agent_enroll_request_valid() -> None:
    """Test AgentEnrollRequest valid payload."""
    req = AgentEnrollRequest(
        node_id="11111111-2222-3333-4444-555555555555",
        enrollment_token="secret-token-123",
        hostname="node-ubuntu",
    )
    assert req.agent_version == "0.1.0"
    assert req.enrollment_token == "secret-token-123"


def test_agent_enroll_response_interval_range() -> None:
    """Test heartbeat interval bounds validation."""
    now = datetime.now(UTC)
    # Valid interval
    resp = AgentEnrollResponse(
        agent_id="22222222-3333-4444-5555-666666666666",
        node_id="11111111-2222-3333-4444-555555555555",
        heartbeat_interval_seconds=15,
        enrolled_at=now,
    )
    assert resp.heartbeat_interval_seconds == 15

    # Interval less than 1 should fail
    with pytest.raises(ValidationError):
        AgentEnrollResponse(
            agent_id="22222222-3333-4444-5555-666666666666",
            node_id="11111111-2222-3333-4444-555555555555",
            heartbeat_interval_seconds=0,
            enrolled_at=now,
        )

    # Interval greater than 3600 should fail
    with pytest.raises(ValidationError):
        AgentEnrollResponse(
            agent_id="22222222-3333-4444-5555-666666666666",
            node_id="11111111-2222-3333-4444-555555555555",
            heartbeat_interval_seconds=3601,
            enrolled_at=now,
        )


def test_heartbeat_request_and_response() -> None:
    """Test HeartbeatRequest and HeartbeatResponse valid values."""
    now = datetime.now(UTC)
    req = HeartbeatRequest(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        sequence=1,
        sent_at=now,
    )
    assert req.sequence == 1

    resp = HeartbeatResponse(
        status="ok",
        received_at=now,
        next_interval_seconds=10,
    )
    assert resp.status == "ok"


def test_heartbeat_request_sequence_min() -> None:
    """Test that sequence must be >= 1."""
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        HeartbeatRequest(
            node_id="11111111-2222-3333-4444-555555555555",
            agent_id="22222222-3333-4444-5555-666666666666",
            sequence=0,
            sent_at=now,
        )


def test_metric_sample_valid() -> None:
    """Test MetricSample with valid CPU, RAM, Disk and Network metrics."""
    now = datetime.now(UTC)
    sample = MetricSample(
        observed_at=now,
        cpu_percent=45.2,
        memory_percent=60.8,
        disk_percent=33.1,
        network_tx_bytes=1024,
        network_rx_bytes=2048,
    )
    assert sample.cpu_percent == 45.2
    assert sample.memory_percent == 60.8
    assert sample.network_tx_bytes == 1024


def test_metric_sample_invalid_ranges() -> None:
    """Test that CPU > 100% or < 0% raises ValidationError."""
    now = datetime.now(UTC)

    # CPU > 100
    with pytest.raises(ValidationError):
        MetricSample(observed_at=now, cpu_percent=101.0, memory_percent=50.0)

    # CPU < 0
    with pytest.raises(ValidationError):
        MetricSample(observed_at=now, cpu_percent=-1.0, memory_percent=50.0)

    # Memory > 100
    with pytest.raises(ValidationError):
        MetricSample(observed_at=now, cpu_percent=50.0, memory_percent=105.0)

    # Negative network bytes
    with pytest.raises(ValidationError):
        MetricSample(
            observed_at=now,
            cpu_percent=50.0,
            memory_percent=50.0,
            network_tx_bytes=-10,
        )


def test_metric_batch_request_valid() -> None:
    """Test MetricBatchRequest with list of samples."""
    now = datetime.now(UTC)
    sample = MetricSample(observed_at=now, cpu_percent=25.0, memory_percent=40.0)
    batch = MetricBatchRequest(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        sequence=1,
        sent_at=now,
        samples=[sample],
    )
    assert len(batch.samples) == 1
    assert batch.samples[0].cpu_percent == 25.0


def test_metric_batch_request_empty_samples() -> None:
    """Test that empty samples list raises ValidationError."""
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        MetricBatchRequest(
            node_id="11111111-2222-3333-4444-555555555555",
            agent_id="22222222-3333-4444-5555-666666666666",
            sequence=1,
            sent_at=now,
            samples=[],
        )


def test_metric_batch_response_valid() -> None:
    """Test MetricBatchResponse with processed count."""
    now = datetime.now(UTC)
    resp = MetricBatchResponse(status="ok", processed_count=5, received_at=now)
    assert resp.status == "ok"
    assert resp.processed_count == 5
