"""Operational CLI must preserve identity and avoid leaking enrollment secrets."""

import asyncio
import io
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sentinelx_agent import cli
from sentinelx_agent.client import ControllerClient, ControllerClientError
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.daemon import AgentDaemon
from sentinelx_agent.identity import AgentIdentity, AgentIdentityManager
from sentinelx_common.contracts.agents import AgentEnrollResponse

NODE = "11111111-2222-3333-4444-555555555555"


def configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AgentSettings:
    settings = AgentSettings(node_id=NODE, identity_path=tmp_path / "identity.json")
    monkeypatch.setattr(AgentSettings, "load", lambda _: settings)
    return settings


def test_check_requires_enrollment_but_supports_install_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configuration(tmp_path, monkeypatch)
    assert cli.main(["check"]) == 78
    assert cli.main(["check", "--allow-unenrolled"]) == 0
    assert json.loads(capsys.readouterr().out)["enrolled"] is False


@pytest.mark.parametrize("contents", ["broken-json", '{"agent_id": "private-secret"}'])
def test_corrupt_identity_is_not_overwritten_or_logged(
    contents: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = configuration(tmp_path, monkeypatch)
    settings.identity_path.write_text(contents, encoding="utf-8")
    assert cli.main(["check", "--allow-unenrolled"]) == 78
    assert settings.identity_path.read_text() == contents
    assert "private-secret" not in caplog.text + capsys.readouterr().err


def test_check_refuses_identity_for_another_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = configuration(tmp_path, monkeypatch)
    AgentIdentityManager.save(
        settings.identity_path,
        AgentIdentity(
            node_id="22222222-2222-3333-4444-555555555555",
            agent_id="private-credential",
            enrolled_at=datetime.now(UTC),
        ),
    )
    assert cli.main(["check"]) == 78


def test_stdin_enrollment_saves_private_identity_without_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = configuration(tmp_path, monkeypatch)
    client = AsyncMock(spec=ControllerClient)
    client.__aenter__.return_value = client
    client.enroll.return_value = AgentEnrollResponse(
        node_id=NODE,
        agent_id="22222222-3333-4444-5555-666666666666",
        status="enrolled",
        heartbeat_interval_seconds=10,
        enrolled_at=datetime.now(UTC),
    )
    monkeypatch.setattr(cli, "ControllerClient", lambda *args: client)
    monkeypatch.setattr(sys, "stdin", io.StringIO("private-enrollment-token\n"))
    assert cli.main(["enroll", "--token-stdin"]) == 0
    assert settings.enrollment_token is None
    assert "private-enrollment-token" not in settings.identity_path.read_text()
    assert "private-enrollment-token" not in capsys.readouterr().out
    if os.name == "posix":
        assert settings.identity_path.stat().st_mode & 0o777 == 0o600
    before = settings.identity_path.read_bytes()
    assert cli.main(["enroll", "--token-stdin"]) == 78
    assert settings.identity_path.read_bytes() == before
    client.enroll.assert_awaited_once()


def test_enrollment_error_does_not_echo_controller_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configuration(tmp_path, monkeypatch)
    enroll = AsyncMock(side_effect=ControllerClientError(403, "private-token-echo"))
    monkeypatch.setattr(cli, "enroll", enroll)
    monkeypatch.setattr(sys, "stdin", io.StringIO("private-token-echo"))
    assert cli.main(["enroll", "--token-stdin"]) == 1
    assert "private-token-echo" not in str(capsys.readouterr())


def test_yaml_error_does_not_echo_secret_source_line(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text('controller: [private-token: "', encoding="utf-8")
    assert cli.main(["--config", str(path), "check"]) == 78
    assert "private-token" not in str(capsys.readouterr())


def test_default_command_runs_daemon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = configuration(tmp_path, monkeypatch)
    run = AsyncMock()
    monkeypatch.setattr(cli, "run_daemon", run)
    assert cli.main([]) == 0
    run.assert_awaited_once_with(settings)


@pytest.mark.asyncio
async def test_bootstrap_failure_closes_owned_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock(spec=ControllerClient)
    monkeypatch.setattr("sentinelx_agent.daemon.ControllerClient", lambda **kwargs: client)
    daemon = AgentDaemon(AgentSettings(identity_path=tmp_path / "id.json"))
    with pytest.raises(RuntimeError, match="Cannot enroll"):
        await daemon.run()
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancellation_stops_sibling_loops_and_closes_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = AgentSettings(identity_path=tmp_path / "identity.json")
    AgentIdentityManager.save(
        settings.identity_path,
        AgentIdentity(
            node_id=NODE,
            agent_id="credential",
            enrolled_at=datetime.now(UTC),
        ),
    )
    client = AsyncMock(spec=ControllerClient)
    monkeypatch.setattr("sentinelx_agent.daemon.ControllerClient", lambda **kwargs: client)
    entered = asyncio.Event()
    exited = asyncio.Event()

    async def heartbeat() -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            exited.set()

    daemon = AgentDaemon(settings)
    monkeypatch.setattr(daemon, "_heartbeat_loop", heartbeat)
    running = asyncio.create_task(daemon.run())
    await asyncio.wait_for(entered.wait(), timeout=2)
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert exited.is_set()
    client.close.assert_awaited_once()
