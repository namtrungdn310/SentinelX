"""Owned nftables sets, verified JSON schema and absolute-expiry reconciliation."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_common.contracts.command_parameters import normalize_command
from sentinelx_common.contracts.defense import AgentCommandContract

CommandRunner = Callable[[list[str], str | None], Awaitable[tuple[int, str, str]]]


async def _default_command_runner(
    cmd: list[str],
    stdin_text: str | None = None,
    timeout: float = 5.0,
) -> tuple[int, str, str]:
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(stdin_text.encode() if stdin_text is not None else None),
            timeout,
        )
        return (
            proc.returncode or 0,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )
    except (TimeoutError, asyncio.CancelledError) as error:
        if proc is not None:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
        if isinstance(error, asyncio.CancelledError):
            raise
        return -1, "", f"Command timed out after {timeout}s"
    except OSError as error:
        return -1, "", f"Cannot execute {cmd[0]}: {type(error).__name__}"


class NftablesDefenseExecutor(BaseDefenseExecutor):
    def __init__(
        self,
        table_name: str = "sentinelx",
        nft_bin: str = "nft",
        command_runner: CommandRunner | None = None,
        timeout_seconds: float = 5.0,
        hook: str = "input",
    ) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,31}", table_name):
            raise ValueError("Invalid nftables table identifier")
        if hook not in {"input", "forward"}:
            raise ValueError("Only input or forward protection is supported")
        self.table_name, self.nft_bin, self.hook = table_name, nft_bin, hook
        self.timeout_seconds = timeout_seconds
        self._command_runner = command_runner or (
            lambda cmd, stdin: _default_command_runner(cmd, stdin, timeout_seconds)
        )
        self._init_lock = asyncio.Lock()

    def build_init_script(self) -> str:
        return (
            f"table inet {self.table_name} {{\n"
            " set blocked_v4 { type ipv4_addr; flags timeout; size 10000; }\n"
            " set blocked_v6 { type ipv6_addr; flags timeout; size 10000; }\n"
            f" chain guard {{ type filter hook {self.hook} priority -100; policy accept;\n"
            "  ip saddr @blocked_v4 drop\n"
            "  ip6 saddr @blocked_v6 drop\n"
            " }\n}\n"
        )

    async def _schema(self) -> tuple[list[dict[str, Any]] | None, str]:
        code, output, error = await self._command_runner(
            [self.nft_bin, "-j", "list", "table", "inet", self.table_name],
            None,
        )
        if code != 0:
            return None, error
        try:
            value = json.loads(output)["nftables"]
            if not isinstance(value, list):
                raise ValueError("Invalid schema")
            return value, ""
        except (ValueError, KeyError, TypeError):
            return None, "Invalid nftables JSON response"

    def _validate_schema(self, objects: list[dict[str, Any]]) -> tuple[bool, str | None]:
        tables = [item["table"] for item in objects if "table" in item]
        if not any(
            table.get("family") == "inet"
            and table.get("name") == self.table_name
            and "dormant" not in table.get("flags", [])
            for table in tables
        ):
            return False, "Missing active owned table"
        sets = {item["set"]["name"]: item["set"] for item in objects if "set" in item}
        for name, kind in (("blocked_v4", "ipv4_addr"), ("blocked_v6", "ipv6_addr")):
            obj = sets.get(name, {})
            if (
                obj.get("type") != kind
                or set(obj.get("flags", [])) != {"timeout"}
                or not 1 <= obj.get("size", 0) <= 10000
            ):
                return False, f"Missing/incompatible timeout set: {name}"
        chains = [
            item["chain"]
            for item in objects
            if "chain" in item
            and item["chain"].get("hook") == self.hook
            and item["chain"].get("type") == "filter"
            and item["chain"].get("prio") == -100
            and item["chain"].get("policy") == "accept"
        ]
        for chain in chains:
            protected: set[str] = set()
            rules = [
                item["rule"]
                for item in objects
                if "rule" in item and item["rule"].get("chain") == chain["name"]
            ]
            if len(rules) != 2:
                continue  # An earlier accept/jump could bypass a later set drop.
            for item in objects:
                rule = item.get("rule", {})
                if rule.get("chain") != chain["name"]:
                    continue
                expressions = rule.get("expr", [])
                # Require an unconditional address-set membership followed by drop.
                if len(expressions) != 2 or expressions[1] != {"drop": None}:
                    continue
                match = expressions[0].get("match", {})
                for protocol, set_name in (("ip", "blocked_v4"), ("ip6", "blocked_v6")):
                    if (
                        match.get("op") == "=="
                        and match.get("left")
                        == {"payload": {"protocol": protocol, "field": "saddr"}}
                        and match.get("right") == "@" + set_name
                    ):
                        protected.add(set_name)
            if protected == {"blocked_v4", "blocked_v6"}:
                return True, None
        return False, "Missing verified IPv4/IPv6 drop rules on the configured base hook"

    async def ensure_initialized(self) -> tuple[bool, str | None]:
        objects, error = await self._schema()
        if objects is not None:
            # Never overwrite an operator's incompatible table or flush other firewall rules.
            return self._validate_schema(objects)
        if "No such file or directory" not in error and "does not exist" not in error:
            return False, error or "Cannot inspect nftables schema"
        code, _, error = await self._command_runner(
            [self.nft_bin, "-f", "-"],
            self.build_init_script(),
        )
        if code != 0:
            return False, error
        objects, error = await self._schema()
        return self._validate_schema(objects) if objects is not None else (False, error)

    async def _element(
        self,
        target: str,
        name: str,
    ) -> tuple[bool, dict[str, Any] | None, str]:
        code, output, error = await self._command_runner(
            [
                self.nft_bin,
                "-j",
                "list",
                "set",
                "inet",
                self.table_name,
                name,
            ],
            None,
        )
        if code != 0:
            if "No such file or directory" in error or "does not exist" in error:
                return True, None, ""
            return False, None, error
        try:
            for item in json.loads(output)["nftables"]:
                if "set" not in item:
                    continue
                for element in item.get("set", {}).get("elem", []):
                    if isinstance(element, str) and element == target:
                        return True, {"val": target}, ""
                    if isinstance(element, dict):
                        value = element.get("elem", element)
                        if isinstance(value, dict) and str(value.get("val")) == target:
                            return True, value, ""
                return True, None, ""
            return False, None, "Cannot inspect the owned nftables set"
        except (ValueError, KeyError, TypeError):
            return False, None, "Invalid nftables element JSON"

    async def execute(self, command: AgentCommandContract) -> ExecutionResult:
        if command.action_type not in {"BLOCK_IP_NFTABLES", "UNBLOCK_IP_NFTABLES"}:
            return ExecutionResult(success=False, error_message="Unsupported nftables action")
        try:
            target, parameters = normalize_command(
                command.action_type,
                command.target_ip,
                command.command_payload,
            )
            assert target is not None
            owner = str(UUID(command.id))
            name = "blocked_v4" if ipaddress.ip_address(target).version == 4 else "blocked_v6"
        except (ValueError, AssertionError) as validation_error:
            return ExecutionResult(success=False, error_message=str(validation_error))
        async with self._init_lock:
            ready, error = await self.ensure_initialized()
            if not ready:
                return ExecutionResult(success=False, error_message=error)
            inspected, element, error = await self._element(target, name)
            if not inspected:
                return ExecutionResult(success=False, error_message=error)
            if command.action_type == "UNBLOCK_IP_NFTABLES":
                original = parameters.get("original_defense_action_id")
                if not original:
                    return ExecutionResult(
                        success=False, error_message="Unblock requires ownership"
                    )
                if element is not None and element.get("comment") != str(original):
                    return ExecutionResult(
                        success=False, error_message="Target has a different owner"
                    )
                if element is None:
                    return ExecutionResult(
                        success=True,
                        metadata={"executor": "nftables", "already_removed": True},
                    )
                script = f"delete element inet {self.table_name} {name} {{ {target} }}\n"
            else:
                deadline = datetime.now(UTC) + timedelta(seconds=parameters["duration_seconds"])
                if "effective_until" in parameters:
                    deadline = datetime.fromisoformat(parameters["effective_until"])
                    if deadline.tzinfo is None:
                        return ExecutionResult(
                            success=False, error_message="Expiry must be timezone aware"
                        )
                remaining = math.ceil((deadline - datetime.now(UTC)).total_seconds())
                if remaining <= 0:
                    return ExecutionResult(
                        success=False, error_message="Block's effective period expired"
                    )
                if remaining > parameters["duration_seconds"]:
                    return ExecutionResult(
                        success=False, error_message="Expiry exceeds block duration"
                    )
                if element is not None and element.get("comment") != owner:
                    return ExecutionResult(
                        success=False, error_message="Target already has a different owner"
                    )
                script = ""
                if element is not None:
                    script += f"delete element inet {self.table_name} {name} {{ {target} }}\n"
                script += (
                    f"add element inet {self.table_name} {name} "
                    f'{{ {target} timeout {remaining}s comment "{owner}" }}\n'
                )
            code, _, error = await self._command_runner([self.nft_bin, "-f", "-"], script)
            if code:
                return ExecutionResult(success=False, error_message=error)
            checked, after, error = await self._element(target, name)
            expected = (
                after is not None and after.get("comment") == owner
                if command.action_type == "BLOCK_IP_NFTABLES"
                else after is None
            )
            if not checked or not expected:
                return ExecutionResult(
                    success=False, error_message=error or "Kernel state verification failed"
                )
            return ExecutionResult(
                success=True,
                metadata={
                    "executor": "nftables",
                    "table": self.table_name,
                    "set": name,
                    "target_ip": target,
                    "owner": owner,
                    "hook": self.hook,
                    "effective_until": parameters.get("effective_until"),
                },
            )
