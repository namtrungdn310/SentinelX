"""Unit tests for AgentIdentityManager."""

from datetime import UTC, datetime
from pathlib import Path

from sentinelx_agent.identity import AgentIdentity, AgentIdentityManager


def test_agent_identity_save_and_load(tmp_path: Path) -> None:
    """Test saving agent identity to file and reloading it."""
    file_path = tmp_path / "subdir" / "agent_identity.json"
    now = datetime.now(UTC)

    identity = AgentIdentity(
        node_id="11111111-2222-3333-4444-555555555555",
        agent_id="22222222-3333-4444-5555-666666666666",
        status="enrolled",
        enrolled_at=now,
    )

    AgentIdentityManager.save(file_path, identity)
    assert file_path.is_file()

    loaded = AgentIdentityManager.load(file_path)
    assert loaded is not None
    assert loaded.node_id == identity.node_id
    assert loaded.agent_id == identity.agent_id
    assert loaded.status == "enrolled"


def test_agent_identity_load_nonexistent_returns_none(tmp_path: Path) -> None:
    """Test loading from non-existent file returns None."""
    file_path = tmp_path / "missing.json"
    assert AgentIdentityManager.load(file_path) is None


def test_agent_identity_load_corrupted_returns_none(tmp_path: Path) -> None:
    """Test loading corrupted json file returns None."""
    file_path = tmp_path / "corrupt.json"
    file_path.write_text("not-a-valid-json", encoding="utf-8")
    assert AgentIdentityManager.load(file_path) is None
