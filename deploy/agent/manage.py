"""Linux Agent installation manager, usable with distro Python 3.10+ and uv.

Run from a trusted extracted bundle. Does not download or execute installer scripts.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

CAPTURE_OVERRIDE = (
    "# Managed by SentinelX: opt-in M2 capture, no promiscuous mode.\n"
    "[Service]\nCapabilityBoundingSet=CAP_NET_RAW\nAmbientCapabilities=CAP_NET_RAW\n"
    "RestrictAddressFamilies=AF_PACKET AF_NETLINK\n"
)


@dataclass(frozen=True)
class Layout:
    name: str
    root: Path = Path("/")

    def __post_init__(self) -> None:
        if not re.fullmatch(r"sentinelx-agent(?:-[a-z0-9][a-z0-9-]{0,30})?", self.name):
            raise ValueError("Service name must be sentinelx-agent or sentinelx-agent-<suffix>")

    @property
    def prefix(self) -> Path:
        return self.root / "opt" / self.name

    @property
    def config(self) -> Path:
        return self.root / "etc" / self.name

    @property
    def state(self) -> Path:
        return self.root / "var/lib" / self.name

    @property
    def unit(self) -> Path:
        return self.root / "etc/systemd/system" / f"{self.name}.service"

    @property
    def marker(self) -> Path:
        return self.prefix / ".sentinelx-managed"


def execute(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, **kwargs)


def verify_bundle(bundle: Path) -> dict[str, Any]:
    """Reject traversal, symlinked files and damaged local artifacts before root writes."""
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != 1
        or not isinstance(manifest.get("release"), str)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{12}", manifest.get("release", ""))
    ):
        raise ValueError("Unsupported bundle manifest/release")
    files = manifest.get("files")
    required = {"requirements.txt", "service.in", "manage.py", "src/sentinelx_agent/main.py"}
    if not isinstance(files, dict) or not required <= files.keys():
        raise ValueError("Incomplete bundle")
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]
    if not manifest["release"].endswith("-" + digest):
        raise ValueError("Release ID does not match the manifest")
    for name, digest in files.items():
        part = PurePosixPath(name)
        if (
            part.is_absolute()
            or ".." in part.parts
            or "\\" in name
            or not part.parts
            or ":" in name
        ):
            raise ValueError("Unsafe bundle path")
        path = bundle / name
        if (
            not path.is_file()
            or path.is_symlink()
            or not path.resolve().is_relative_to(bundle.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Bundle integrity verification failed")
    return manifest


def atomic_write(path: Path, content: str, mode: int, gid: int = -1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as file:
        temporary = Path(file.name)
        try:
            file.write(content)
            file.flush()
            os.fchmod(file.fileno(), mode)
            if gid != -1:
                os.fchown(file.fileno(), 0, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def managed(layout: Layout) -> None:
    if (
        layout.prefix.is_symlink()
        or layout.config.is_symlink()
        or layout.state.is_symlink()
        or layout.marker.is_symlink()
        or not layout.marker.is_file()
        or layout.marker.read_text().strip() != layout.name
    ):
        raise ValueError("Target is not a recognized SentinelX-managed installation")


def capture_permissions(layout: Layout, enabled: bool) -> None:
    """Manage only our fixed-name systemd override; never edit unrelated overrides."""
    directory = layout.unit.with_name(layout.name + ".service.d")
    override = directory / "50-sentinelx-network.conf"
    if directory.is_symlink() or override.is_symlink():
        raise ValueError("Capture override must not be a symbolic link")
    if override.exists() and override.read_text() != CAPTURE_OVERRIDE:
        raise ValueError("Capture override was customized; refusing to overwrite/remove it")
    if enabled:
        atomic_write(override, CAPTURE_OVERRIDE, 0o644)
    else:
        override.unlink(missing_ok=True)
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def account(layout: Layout) -> tuple[int, int]:
    import pwd

    try:
        user = pwd.getpwnam(layout.name)
        if user.pw_uid == 0 or user.pw_dir != str(layout.state):
            raise ValueError("Existing account is not the expected dedicated service account")
    except KeyError:
        execute(
            [
                "useradd",
                "--system",
                "--user-group",
                "--home-dir",
                str(layout.state),
                "--shell",
                "/usr/sbin/nologin",
                layout.name,
            ]
        )
        user = pwd.getpwnam(layout.name)
    return user.pw_uid, user.pw_gid


def local_command(layout: Layout, args: list[str], token: str | None = None) -> None:
    env = {
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(layout.prefix / "current/src"),
    }
    command = ["runuser", "-u", layout.name, "--", "env", "-i"]
    command += [f"{key}={value}" for key, value in env.items()]
    command += [
        str(layout.prefix / "current/.venv/bin/python"),
        "-m",
        "sentinelx_agent.main",
        "--config",
        str(layout.config / "agent.yaml"),
        *args,
    ]
    execute(command, input=token, cwd=layout.state)


def switch(layout: Layout, release: Path, link: str = "current") -> None:
    releases = layout.prefix / "releases"
    if (
        release.is_symlink()
        or not release.is_dir()
        or release.resolve().parent != releases.resolve()
    ):
        raise ValueError("Release must be inside this installation's releases directory")
    temporary = layout.prefix / f".{link}-next"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(Path("releases") / release.name)
    os.replace(temporary, layout.prefix / link)


def release_at(layout: Layout, link: str) -> Path | None:
    pointer = layout.prefix / link
    if not pointer.is_symlink():
        if pointer.exists():
            raise ValueError("Release pointer is not a symlink")
        return None
    target = pointer.resolve(strict=True)
    if target.parent != (layout.prefix / "releases").resolve() or not target.is_dir():
        raise ValueError("Release pointer escapes this installation")
    return target


def install(layout: Layout, args: argparse.Namespace) -> None:
    for command in ("systemctl", "systemd-analyze", "runuser", "useradd"):
        if shutil.which(command) is None:
            raise ValueError(f"Required Linux command is missing: {command}")
    if not Path("/run/systemd/system").is_dir():
        raise ValueError("A running systemd host is required")
    bundle = args.bundle.resolve()
    manifest = verify_bundle(bundle)
    fresh = not layout.marker.exists()
    if fresh:
        if any(
            path.exists() or path.is_symlink()
            for path in (layout.prefix, layout.config, layout.state, layout.unit)
        ):
            raise ValueError("Refusing to overwrite an existing unmanaged path")
        if not args.controller_url or not args.node_id:
            raise ValueError("Fresh install requires --controller-url and --node-id")
        parsed = urlsplit(args.controller_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Controller URL must be HTTP(S), without credentials/query/fragment")
        node_id = str(UUID(args.node_id))
    else:
        managed(layout)
        if args.controller_url or args.node_id:
            raise ValueError("Update preserves configuration; edit it explicitly before restarting")
    uv = shutil.which(args.uv)
    if uv is None:
        raise ValueError("uv not found; install it separately or pass --uv /absolute/path")
    uid, gid = account(layout)
    layout.prefix.mkdir(parents=True, mode=0o755, exist_ok=True)
    if fresh:
        atomic_write(layout.marker, layout.name + "\n", 0o644)
        layout.config.mkdir(mode=0o750, parents=True)
        os.chown(layout.config, 0, gid)
        layout.state.mkdir(mode=0o700, parents=True)
        os.chown(layout.state, uid, gid)
        config = {
            "controller": {"url": args.controller_url.rstrip("/")},
            "agent": {
                "node_id": node_id,
                "telemetry_collector_type": "real",
                "telemetry_interval_seconds": 5,
                "telemetry_batch_size": 5,
                "telemetry_disk_path": "/",
                "identity_path": str(layout.state / "identity.json"),
            },
        }
        atomic_write(layout.config / "agent.yaml", json.dumps(config, indent=2) + "\n", 0o640, gid)
    releases = layout.prefix / "releases"
    releases.mkdir(mode=0o755, exist_ok=True)
    release = releases / manifest["release"]
    if release.is_symlink() or releases.is_symlink():
        raise ValueError("Release directory must not be a symbolic link")
    # A failed dependency download can leave an incomplete, never-activated release.
    if release.exists() and not (release / "manifest.json").is_file():
        if release_at(layout, "current") == release.resolve():
            raise ValueError("Active release is incomplete; restore a trusted bundle")
        shutil.rmtree(release)
    if release.exists():
        verify_bundle(release)
    else:
        release.mkdir(mode=0o755)
        for name in manifest["files"]:
            destination = release / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle / name, destination)
            destination.chmod(0o644)
        environment = os.environ.copy()
        environment.update(
            {
                "UV_PYTHON_INSTALL_DIR": str(layout.prefix / "python"),
                "UV_CACHE_DIR": str(layout.prefix / "cache"),
            }
        )
        execute(
            [uv, "venv", "--python", "3.12", "--managed-python", str(release / ".venv")],
            env=environment,
        )
        execute(
            [
                uv,
                "pip",
                "sync",
                "--python",
                str(release / ".venv/bin/python"),
                "--require-hashes",
                str(release / "requirements.txt"),
            ],
            env=environment,
        )
        shutil.copyfile(bundle / "manifest.json", release / "manifest.json")
    old = release_at(layout, "current")
    old_unit = layout.unit.read_text(encoding="utf-8") if layout.unit.is_file() else None
    unit = (release / "service.in").read_text(encoding="utf-8")
    for key, value in {
        "NAME": layout.name,
        "PREFIX": str(layout.prefix),
        "CONFIG": str(layout.config),
        "STATE": str(layout.state),
    }.items():
        unit = unit.replace(f"__{key}__", value)
    try:
        switch(layout, release)
        atomic_write(layout.unit, unit, 0o644)
        execute(["systemd-analyze", "verify", str(layout.unit)])
        local_command(layout, ["check", "--allow-unenrolled"])
        if args.token_file:
            enroll_installation(layout, args.token_file)
        execute(["systemctl", "daemon-reload"])
        if not args.no_start:
            local_command(layout, ["check"])
        execute(["systemctl", "enable", f"{layout.name}.service"])
        if not args.no_start:
            execute(["systemctl", "restart", f"{layout.name}.service"])
        if old and old != release:
            switch(layout, old, "previous")
    except Exception:
        if old:
            switch(layout, old)
            if old_unit is not None:
                atomic_write(layout.unit, old_unit, 0o644)
                execute(["systemctl", "daemon-reload"])
            execute(["systemctl", "restart", f"{layout.name}.service"])
        raise
    print(f"Installed {manifest['release']}; config and identity kept outside the release.")


def enroll_installation(layout: Layout, token_file: Path | None) -> None:
    managed(layout)
    if token_file:
        if token_file.is_symlink() or token_file.stat().st_mode & 0o077:
            raise ValueError("Token file must be a regular private file (chmod 600)")
        token = token_file.read_text(encoding="utf-8")
    else:
        import getpass

        token = getpass.getpass("Enrollment token: ")
    if not token.strip() or len(token) > 4096:
        raise ValueError("Enrollment token is empty or too long")
    local_command(layout, ["enroll", "--token-stdin"], token=token)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="sentinelx-agent", help="Dedicated service/account name")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("install", "update"):
        command = sub.add_parser(action)
        command.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
        command.add_argument("--uv", default="uv")
        command.add_argument("--controller-url")
        command.add_argument("--node-id")
        command.add_argument("--token-file", type=Path)
        command.add_argument("--no-start", action="store_true")
    registration = sub.add_parser("enroll")
    registration.add_argument("--token-file", type=Path)
    capture = sub.add_parser("capture-permissions", help="Opt in/out of CAP_NET_RAW for M2")
    capture_choice = capture.add_mutually_exclusive_group(required=True)
    capture_choice.add_argument("--enable", action="store_true")
    capture_choice.add_argument("--disable", action="store_true")
    for action in ("check", "status", "restart", "rollback", "uninstall"):
        command = sub.add_parser(action)
        if action == "uninstall":
            command.add_argument("--purge", action="store_true", help="Also remove config/identity")
    args = parser.parse_args()
    try:
        if sys.platform != "linux" or os.geteuid() != 0:
            raise ValueError("Run this manager as root on a systemd Linux host")
        layout = Layout(args.name)
        if args.action in {"install", "update"}:
            if args.action == "update":
                managed(layout)
            install(layout, args)
        else:
            managed(layout)
            if args.action == "enroll":
                enroll_installation(layout, args.token_file)
            elif args.action == "check":
                local_command(layout, ["check"])
            elif args.action == "status":
                execute(["systemctl", "status", "--no-pager", f"{layout.name}.service"])
            elif args.action == "restart":
                local_command(layout, ["check"])
                execute(["systemctl", "restart", f"{layout.name}.service"])
            elif args.action == "capture-permissions":
                capture_permissions(layout, args.enable)
                execute(["systemctl", "daemon-reload"])
                print(
                    "Capture permissions updated; configure capture, then restart explicitly."
                )
            elif args.action == "rollback":
                previous = release_at(layout, "previous")
                current = release_at(layout, "current")
                if previous is None or current is None:
                    raise ValueError("No previous release available")
                verify_bundle(previous)
                switch(layout, previous)
                try:
                    local_command(layout, ["check"])
                    execute(["systemctl", "restart", f"{layout.name}.service"])
                except Exception:
                    switch(layout, current)
                    execute(["systemctl", "restart", f"{layout.name}.service"])
                    raise
                switch(layout, current, "previous")
            else:
                if layout.unit.is_file():
                    execute(["systemctl", "disable", "--now", f"{layout.name}.service"])
                layout.unit.unlink(missing_ok=True)
                capture_permissions(layout, False)
                execute(["systemctl", "daemon-reload"])
                # Only a marked, fixed-name installation is removable. Never follow symlinks.
                if args.purge:
                    shutil.rmtree(layout.prefix)
                    shutil.rmtree(layout.config)
                    shutil.rmtree(layout.state)
                    execute(["userdel", layout.name])
                else:
                    # Retain the ownership marker so reinstall can safely reuse config/identity.
                    for child in layout.prefix.iterdir():
                        if child == layout.marker:
                            continue
                        if child.is_dir() and not child.is_symlink():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
                print(
                    "Agent removed. "
                    + (
                        "Identity/config purged."
                        if args.purge
                        else "Identity/config and account retained for recovery; keep a backup."
                    )
                )
        return 0
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, subprocess.CalledProcessError):
        print(
            "Agent operation failed; check prerequisites, permissions and journal. "
            "No enrollment token is printed.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
