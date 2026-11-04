"""Build a standalone Agent-only source bundle with hash-locked uv dependencies."""

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
import tomllib
from pathlib import Path

PRUNED = ("fastapi", "uvicorn", "sqlalchemy", "asyncpg", "alembic")


def build(source: Path, output: Path, uv: str = "uv") -> Path:
    source = source.resolve()
    command = [
        uv,
        "--no-cache",
        "export",
        "--frozen",
        "--no-dev",
        "--no-emit-project",
        "--no-header",
    ]
    for package in PRUNED:
        command.extend(["--prune", package])
    requirements = subprocess.run(
        command,
        cwd=source,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    files: dict[str, bytes] = {"requirements.txt": requirements}
    for package in ("sentinelx_agent", "sentinelx_common"):
        for path in sorted((source / "src" / package).rglob("*.py")):
            if path.is_symlink():
                raise ValueError("Source package must not contain symbolic links")
            files[path.relative_to(source).as_posix()] = path.read_bytes()
    for name, path in {
        "manage.py": source / "deploy/agent/manage.py",
        "service.in": source / "deploy/agent/sentinelx-agent.service.in",
        "README.md": source / "docs/AGENT_INSTALLATION.md",
    }.items():
        files[name] = path.read_bytes()
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:12]
    project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    release = f"{version}-{digest}"
    manifest = {"format": 1, "release": release, "files": hashes}
    files["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"sentinelx-agent-{release}.tar.gz"
    if archive.exists():
        raise FileExistsError(f"Bundle already exists: {archive}")
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in sorted(files.items()):
            entry = tarfile.TarInfo(f"sentinelx-agent-{release}/{name}")
            entry.size = len(content)
            entry.mode = 0o644
            entry.mtime = 0
            tar.addfile(entry, io.BytesIO(content))
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("dist/agent"))
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    print(build(args.source, args.output, args.uv))


if __name__ == "__main__":
    main()
