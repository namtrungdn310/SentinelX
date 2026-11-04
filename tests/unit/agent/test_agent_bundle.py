"""Bundle validation protects privileged installation and keeps the Agent standalone."""

import hashlib
import importlib.util
import json
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


manager = load_module("agent_install_manager", ROOT / "deploy/agent/manage.py")
builder = load_module("agent_bundle_builder", ROOT / "scripts/build_agent_bundle.py")


def bundle(tmp_path: Path, **extra: bytes) -> Path:
    files = {
        "manage.py": b"# manager",
        "requirements.txt": b"",
        "service.in": b"# unit",
        "src/sentinelx_agent/main.py": b"# agent",
        **extra,
    }
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:12]
    for name, value in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "format": 1,
                "release": f"0.1.0-{digest}",
                "files": hashes,
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_bundle_integrity_detects_modified_file(tmp_path: Path) -> None:
    artifact = bundle(tmp_path)
    assert manager.verify_bundle(artifact)["format"] == 1
    (artifact / "manage.py").write_text("# altered", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        manager.verify_bundle(artifact)


def test_bundle_refuses_path_traversal(tmp_path: Path) -> None:
    artifact = bundle(tmp_path / "bundle", **{"../escape.py": b"escape"})
    with pytest.raises(ValueError, match="Unsafe bundle path"):
        manager.verify_bundle(artifact)


def test_bundle_refuses_incomplete_manifest_and_forged_release(tmp_path: Path) -> None:
    artifact = bundle(tmp_path)
    path = artifact / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["release"] = "0.1.0-000000000000"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Release ID"):
        manager.verify_bundle(artifact)
    invalid_manifests: list[object] = [[], {"format": 1, "release": None}]
    for invalid in invalid_manifests:
        path.write_text(json.dumps(invalid), encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            manager.verify_bundle(artifact)


@pytest.mark.parametrize("name", ["../agent", "sshd", "sentinelx-agent/../../etc"])
def test_manager_refuses_unscoped_service_names(name: str) -> None:
    with pytest.raises(ValueError):
        manager.Layout(name)


def test_manager_refuses_unmarked_installation(tmp_path: Path) -> None:
    layout = manager.Layout("sentinelx-agent-qa", root=tmp_path)
    layout.prefix.mkdir(parents=True)
    with pytest.raises(ValueError, match="not a recognized"):
        manager.managed(layout)


def test_build_contains_only_agent_common_and_locked_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Export:
        stdout = b"psutil==7.2.2 --hash=sha256:fixture\n"

    commands: list[list[str]] = []

    def export(command: list[str], **kwargs: object) -> Export:
        commands.append(command)
        return Export()

    monkeypatch.setattr(builder.subprocess, "run", export)
    archive = builder.build(ROOT, tmp_path)
    with tarfile.open(archive) as tar:
        names = [member.name for member in tar.getmembers()]
        assert any("/src/sentinelx_agent/cli.py" in name for name in names)
        assert any("/src/sentinelx_common/contracts/telemetry.py" in name for name in names)
        assert not any("sentinelx_controller" in name or "identity.json" in name for name in names)
        assert all(not name.endswith((".env", ".local.yaml")) for name in names)
    assert "--frozen" in commands[0] and "--no-dev" in commands[0]
    for dependency in ("fastapi", "uvicorn", "sqlalchemy", "asyncpg", "alembic"):
        assert dependency in commands[0]
