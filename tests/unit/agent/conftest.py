"""Agent unit tests never share a journal or write runtime state into the repository."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINELX_COMMAND_JOURNAL_PATH", str(tmp_path / "commands.sqlite3"))
