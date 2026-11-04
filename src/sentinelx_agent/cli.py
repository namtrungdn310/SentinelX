"""Agent commands for foreground service execution and one-time enrollment."""

import argparse
import asyncio
import getpass
import json
import logging
import os
import signal
import sys
from pathlib import Path

import aiohttp
from pydantic import ValidationError

from sentinelx_agent.client import ControllerClient, ControllerClientError
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.daemon import AgentDaemon
from sentinelx_agent.identity import AgentIdentity, AgentIdentityManager
from sentinelx_common.config.yaml_loader import ConfigLoadError

CONFIG_ERROR = 78


def checked_identity(settings: AgentSettings) -> AgentIdentity | None:
    """Reject damaged or mismatched identity instead of silently enrolling again."""
    identity = AgentIdentityManager.load(settings.identity_path)
    if settings.identity_path.exists() and identity is None:
        raise ValueError("Identity file is invalid; restore it or explicitly enroll again")
    if identity and settings.node_id and identity.node_id != settings.node_id:
        raise ValueError("Configured node_id does not match the saved identity")
    return identity


async def enroll(settings: AgentSettings, token: str) -> None:
    """Enroll once, close HTTP resources and leave the daemon stopped."""
    if checked_identity(settings) is not None:
        raise ValueError("Already enrolled; existing identity was preserved")
    if not settings.node_id or not token.strip():
        raise ValueError("Enrollment requires node_id and a nonempty token")
    updated = settings.model_copy(update={"enrollment_token": token.strip()})
    async with ControllerClient(updated.controller_url, updated.timeout_seconds) as client:
        daemon = AgentDaemon(updated, client=client)
        await daemon.bootstrap_identity()


async def run_daemon(settings: AgentSettings) -> None:
    """Run until systemd/terminal sends SIGTERM or SIGINT."""
    identity = checked_identity(settings)
    if identity is None and (not settings.node_id or not settings.enrollment_token):
        raise ValueError("Agent is not enrolled; run the enroll command first")
    daemon = AgentDaemon(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    try:
        await daemon.run(stop)
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.remove_signal_handler(sig)
            except NotImplementedError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SentinelX Linux resource Agent")
    parser.add_argument("--config", type=Path, help="Private Agent YAML configuration")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("run", help="Run in foreground (systemd supervises this process)")
    check = commands.add_parser("check", help="Validate local configuration and identity")
    check.add_argument("--allow-unenrolled", action="store_true")
    registration = commands.add_parser("enroll", help="Enroll once without retaining the token")
    source = registration.add_mutually_exclusive_group()
    source.add_argument("--token-file", type=Path)
    source.add_argument("--token-stdin", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=os.getenv("SENTINELX_AGENT_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )
    try:
        settings = AgentSettings.load(args.config or os.getenv("SENTINELX_AGENT_CONFIG"))
        if args.command == "check":
            identity = checked_identity(settings)
            if identity is None and not args.allow_unenrolled:
                raise ValueError("Agent is not enrolled")
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "enrolled": identity is not None,
                        "node_id": identity.node_id if identity else settings.node_id,
                        "collector": settings.telemetry_collector_type,
                        "controller_url": settings.controller_url,
                    }
                )
            )
        elif args.command == "enroll":
            if args.token_file:
                token = args.token_file.read_text(encoding="utf-8")
            elif args.token_stdin:
                token = sys.stdin.read(4096)
            else:
                token = getpass.getpass("Enrollment token: ")
            asyncio.run(enroll(settings, token))
            print("Agent enrolled; identity saved. Enrollment token was not persisted.")
        else:
            asyncio.run(run_daemon(settings))
        return 0
    except ControllerClientError as error:
        # Remote response bodies can echo input; never print them during enrollment.
        print(f"Controller rejected the request (HTTP {error.status_code})", file=sys.stderr)
        return 1
    except (aiohttp.ClientError, TimeoutError):
        print("Cannot reach Controller; check URL, network and TLS configuration", file=sys.stderr)
        return 1
    except ValidationError:
        print("Invalid Agent configuration or Controller response", file=sys.stderr)
        return CONFIG_ERROR
    except ConfigLoadError:
        print("Cannot parse Agent YAML; check syntax and permissions", file=sys.stderr)
        return CONFIG_ERROR
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return CONFIG_ERROR
    except OSError:
        print("Cannot access Agent files; check paths and permissions", file=sys.stderr)
        return CONFIG_ERROR
    except KeyboardInterrupt:
        return 0
