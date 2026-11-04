"""Opt-in Linux/root acceptance using a temporary service and an HTTP contract fixture.

Usage: sudo python3 scripts/test_agent_systemd.py EXTRACTED_BUNDLE --uv /path/to/uv
Creates only sentinelx-agent-qa-<random> resources; purges them in finally. No reboot.
This checks systemd/runtime behavior; real Controller/Postgres acceptance is separate.
"""

import argparse
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, **kwargs)


def wait_until(predicate: Any, description: str, timeout: int = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise AssertionError(f"Timed out: {description}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--uv", required=True)
    args = parser.parse_args()
    if sys.platform != "linux" or os.geteuid() != 0:
        raise SystemExit("This opt-in test requires root on a systemd Linux lab host")
    bundle = args.bundle.resolve()
    name = "sentinelx-agent-qa-" + uuid4().hex[:8]
    prefix = Path("/opt") / name
    state = Path("/var/lib") / name
    config = Path("/etc") / name / "agent.yaml"
    unit = f"{name}.service"
    command = [sys.executable, str(bundle / "manage.py"), "--name", name]
    token = uuid4().hex
    credential = str(uuid4())
    node = str(uuid4())
    stats: dict[str, Any] = {"enroll": 0, "heartbeat": 0, "batches": [], "offline": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass  # No request credentials in the test journal/output.

        def do_POST(self) -> None:
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            now = datetime.now(timezone.utc).isoformat()
            status = 200
            response: dict[str, Any]
            if stats["offline"]:
                status, response = 503, {"detail": "Controlled test outage"}
            elif self.path == "/api/v1/nodes/enroll":
                assert payload["node_id"] == node and payload["enrollment_token"] == token
                stats["enroll"] += 1
                response = {
                    "agent_id": credential,
                    "node_id": node,
                    "status": "enrolled",
                    "heartbeat_interval_seconds": 1,
                    "enrolled_at": now,
                }
            else:
                assert payload["agent_id"] == credential and payload["node_id"] == node
                if self.path == "/api/v1/nodes/heartbeat":
                    stats["heartbeat"] += 1
                    response = {"status": "ok", "received_at": now, "next_interval_seconds": 1}
                elif self.path == "/api/v1/telemetry/metrics":
                    stats["batches"].append(payload)
                    response = {
                        "status": "ok",
                        "received_at": now,
                        "processed_count": len(payload["samples"]),
                    }
                else:
                    status, response = 404, {}
            body = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{server.server_port}"

    def pid() -> str:
        return run(
            ["systemctl", "show", unit, "--property=MainPID", "--value"], capture_output=True
        ).stdout.strip()

    try:
        print(f"QA service: {name}; HTTP fixture on an ephemeral local port", flush=True)
        run(
            [
                *command,
                "install",
                "--controller-url",
                url,
                "--node-id",
                node,
                "--uv",
                args.uv,
                "--no-start",
            ]
        )
        settings = json.loads(config.read_text())
        settings["agent"].update(telemetry_interval_seconds=0.2, telemetry_batch_size=2)
        config.write_text(json.dumps(settings))
        with tempfile.TemporaryDirectory(prefix="sentinelx-agent-qa-") as temporary:
            work = Path(temporary)
            token_file = work / "token"
            token_file.write_text(token)
            token_file.chmod(0o600)
            run([*command, "enroll", "--token-file", str(token_file)])
            token_file.unlink()
            identity = state / "identity.json"
            saved = identity.read_bytes()
            assert identity.stat().st_mode & 0o777 == 0o600
            assert token.encode() not in saved and token not in config.read_text()
            run([*command, "restart"])
            run(["systemctl", "is-enabled", unit])
            wait_until(lambda: len(stats["batches"]) >= 2, "real resource batches")
            first_pid = pid()
            assert first_pid != "0"
            assert Path(f"/proc/{first_pid}").stat().st_uid == pwd.getpwnam(name).pw_uid != 0
            sample = stats["batches"][-1]["samples"][-1]
            assert 0 <= sample["cpu_percent"] <= 100 and 0 <= sample["memory_percent"] <= 100
            assert sample["disk_percent"] is not None
            print("PASS: enrolled, non-root service, private identity, real OS samples", flush=True)

            stats["offline"] = True
            time.sleep(1.5)
            before = len(stats["batches"])
            stats["offline"] = False
            wait_until(lambda: len(stats["batches"]) > before, "reconnect after outage")
            run(["systemctl", "kill", "--signal=SIGKILL", unit])
            wait_until(lambda: pid() not in {"0", first_pid}, "automatic crash restart")
            heartbeats = stats["heartbeat"]
            wait_until(lambda: stats["heartbeat"] > heartbeats, "restarted daemon ready")
            run(["systemctl", "stop", unit])
            result = run(
                ["systemctl", "show", unit, "--property=ExecMainStatus", "--value"],
                capture_output=True,
            )
            assert result.stdout.strip() == "0", "SIGTERM should exit cleanly"
            run(["systemctl", "start", unit])
            wait_until(lambda: pid() != "0", "manual start")
            assert identity.read_bytes() == saved and stats["enroll"] == 1
            print("PASS: network recovery, crash restart, clean stop, identity reuse", flush=True)

            valid_config = config.read_bytes()
            config.write_text('{"agent": {"telemetry_collector_type": "invalid"}}')
            run(["systemctl", "restart", unit])
            wait_until(
                lambda: (
                    run(
                        ["systemctl", "show", unit, "--property=ExecMainStatus", "--value"],
                        capture_output=True,
                    ).stdout.strip()
                    == "78"
                ),
                "configuration error exit",
            )
            assert (
                run(
                    ["systemctl", "show", unit, "--property=ActiveState", "--value"],
                    capture_output=True,
                ).stdout.strip()
                == "failed"
            )
            config.write_bytes(valid_config)
            run(["systemctl", "reset-failed", unit])
            run([*command, "restart"])
            print("PASS: invalid configuration exits 78 without a restart loop", flush=True)

            # Valid second fixture release differs only in bundled documentation.
            alternate = work / "next"
            alternate.mkdir()
            manifest = json.loads((bundle / "manifest.json").read_text())
            for filename in manifest["files"]:
                destination = alternate / filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(bundle / filename, destination)
            readme = alternate / "README.md"
            readme.write_text(readme.read_text() + "\nQA fixture release B.\n")
            manifest["files"]["README.md"] = hashlib.sha256(readme.read_bytes()).hexdigest()
            digest = hashlib.sha256(json.dumps(manifest["files"], sort_keys=True).encode())
            manifest["release"] = "0.1.0-" + digest.hexdigest()[:12]
            (alternate / "manifest.json").write_text(json.dumps(manifest))
            old = (prefix / "current").resolve()
            original_config = config.read_bytes()
            run([*command, "update", "--bundle", str(alternate), "--uv", args.uv])
            assert (prefix / "current").resolve() != old
            assert config.read_bytes() == original_config and identity.read_bytes() == saved
            run([*command, "rollback"])
            assert (prefix / "current").resolve() == old
            run(["systemctl", "reset-failed", unit])
            run([*command, "uninstall"])
            assert identity.read_bytes() == saved and not (prefix / "current").exists()
            run([*command, "install", "--uv", args.uv])
            wait_until(lambda: pid() != "0", "reinstall start")
            assert identity.read_bytes() == saved and stats["enroll"] == 1
            print(
                "PASS: update, rollback, uninstall/reinstall preserve config and identity",
                flush=True,
            )

        logs = run(["journalctl", "-u", unit, "--no-pager"], capture_output=True).stdout
        assert token not in logs and credential not in logs
        print(
            "PASS: no enrollment token/agent credential in journal; boot enabled (no reboot)",
            flush=True,
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        if (prefix / ".sentinelx-managed").is_file():
            run([*command, "uninstall", "--purge"])
        assert not prefix.exists() and not state.exists() and not config.parent.exists()
        assert not (Path("/etc/systemd/system") / unit).exists()
        print(f"QA cleaned: {name}", flush=True)


if __name__ == "__main__":
    main()
