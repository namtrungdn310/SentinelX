"""Real Linux/OS hardware resource collector for SentinelX Agent."""

import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import psutil

from sentinelx_common.contracts.telemetry import MetricSample

logger = logging.getLogger("sentinelx_agent.collectors.real")


class RealResourceCollector:
    """System metrics; call collect in a worker because CPU sampling takes 100ms."""

    def __init__(self, disk_path: str | None = None) -> None:
        self._disk_path = disk_path or self._detect_default_mount()

        self._prev_network = self._read_network()

    @staticmethod
    def _read_network() -> tuple[int, int] | None:
        try:
            net = psutil.net_io_counters()
            return (int(net.bytes_recv), int(net.bytes_sent)) if net else None
        except (OSError, psutil.Error) as err:
            logger.warning("Failed to inspect network counters: %s", err)
            return None

    @staticmethod
    def _detect_default_mount() -> str:
        """Detect default mount point across Linux, macOS, and Windows environments."""
        anchor = Path.home().anchor
        return anchor if anchor else "/"

    @staticmethod
    def _read_cgroup_service(pid: int) -> str | None:
        """Priority 1: Read Linux Cgroup to identify systemd service."""
        try:
            with open(f"/proc/{pid}/cgroup", encoding="utf-8") as f:
                for line in f:
                    if ".service" in line:
                        match = re.search(r"([a-zA-Z0-9_\-\.]+)\.service", line)
                        if match:
                            return f"{match.group(1)}.service"
        except Exception:
            pass
        return None

    @staticmethod
    def _normalize_name_fallback(name: str, cmdline: list[str] | None = None) -> str:
        """Priority 2: Fallback regex normalization and command-line parser."""
        clean = (name or "").strip().lower()
        if clean in ("python", "python3", "node", "java", "ruby") and cmdline:
            for idx, arg in enumerate(cmdline):
                if arg == "-m" and idx + 1 < len(cmdline):
                    clean = cmdline[idx + 1].split(".")[-1].lower()
                    break
                elif arg.endswith((".py", ".js", ".jar")) and not arg.startswith("-"):
                    parts = arg.replace("\\", "/").split("/")
                    clean = parts[-1].split(".")[0].lower()
                    break
        clean = re.sub(r"\[\d+\]|\(\d+\)|#\d+|@[\w\.-]+", "", clean)
        clean = re.sub(r"[-_.\s]*\d+$", "", clean).strip()
        return clean[:64] if clean else (name[:64] if name else "unknown")

    @classmethod
    def _find_top_process(
        cls,
        focus_metric: Literal["auto", "cpu", "memory"] = "auto",
        *,
        normalize_cpu: bool = False,
    ) -> tuple[str | None, int | None, float | None, float | None, int | None, str | None]:
        """Hybrid Process Grouping: Priority 1 (Linux Cgroup) -> Priority 2 (Regex / PPID)."""
        try:
            cpu_divisor = float(os.cpu_count() or 1) if normalize_cpu else 1.0
            groups: dict[str, dict[str, Any]] = {}
            for proc in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_percent", "cmdline"]
            ):
                try:
                    info = proc.info
                    name = str(info.get("name") or "")
                    if name.lower() in ("system idle process", "system", "idle", "registry"):
                        continue
                    pid = int(info["pid"]) if info.get("pid") is not None else 0
                    cpu = float(info.get("cpu_percent") or 0.0) / cpu_divisor
                    if normalize_cpu:
                        cpu = min(100.0, max(0.0, cpu))
                    mem = float(info.get("memory_percent") or 0.0)
                    cmdline = info.get("cmdline") or []

                    # 1. Priority 1: Linux Cgroup inspection
                    cgroup_svc = cls._read_cgroup_service(pid)
                    if cgroup_svc:
                        group_key = f"cgroup:{cgroup_svc}"
                        display_name = cgroup_svc.replace(".service", "")
                    else:
                        # 2. Priority 2: Fallback Regex Normalization
                        display_name = cls._normalize_name_fallback(name, cmdline)
                        group_key = f"proc:{display_name}"

                    if group_key not in groups:
                        groups[group_key] = {
                            "name": display_name,
                            "cgroup": cgroup_svc,
                            "cpu_percent": 0.0,
                            "memory_percent": 0.0,
                            "pids": [],
                        }
                    groups[group_key]["cpu_percent"] += cpu
                    groups[group_key]["memory_percent"] += mem
                    groups[group_key]["pids"].append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            if not groups:
                return None, None, None, None, None, None

            if focus_metric == "cpu":
                top_group = max(
                    groups.values(),
                    key=lambda g: (g["cpu_percent"], g["memory_percent"]),
                )
            elif focus_metric == "memory":
                top_group = max(
                    groups.values(),
                    key=lambda g: (g["memory_percent"], g["cpu_percent"]),
                )
            else:
                top_group = max(
                    groups.values(),
                    key=lambda g: max(g["cpu_percent"], g["memory_percent"]),
                )
            primary_pid = min(top_group["pids"]) if top_group["pids"] else None
            cpu_total = (
                min(100.0, top_group["cpu_percent"])
                if normalize_cpu
                else top_group["cpu_percent"]
            )
            return (
                top_group["name"][:64],
                primary_pid,
                round(cpu_total, 2),
                round(min(100.0, top_group["memory_percent"]), 2),
                len(top_group["pids"]),
                top_group["cgroup"][:128] if top_group["cgroup"] else None,
            )
        except Exception as err:
            logger.debug("Failed to inspect process groups: %s", err)
            return None, None, None, None, None, None

    def collect(self) -> MetricSample:
        """Sample machine resource utilization synchronously.

        This method reads CPU, RAM, Disk, and Network IO counters.
        It is designed to be executed inside a worker thread via asyncio.to_thread.
        """
        # A bounded window is independent of thread-local previous-call state.
        cpu_raw = float(psutil.cpu_percent(interval=0.1))
        cpu_pct = max(0.0, min(100.0, cpu_raw))

        # 2. Memory Usage
        mem = psutil.virtual_memory()
        mem_pct = max(0.0, min(100.0, float(mem.percent)))

        disk_pct: float | None
        try:
            disk = psutil.disk_usage(self._disk_path)
            disk_pct = max(0.0, min(100.0, float(disk.percent)))
        except (PermissionError, FileNotFoundError, OSError) as err:
            logger.warning("Failed to inspect disk usage on %s: %s", self._disk_path, err)
            disk_pct = None

        # 4. Network I/O Delta Calculation
        rx_delta: int | None = None
        tx_delta: int | None = None
        current_network = self._read_network()
        if current_network is not None and self._prev_network is not None:
            rx_delta = max(0, current_network[0] - self._prev_network[0])
            tx_delta = max(0, current_network[1] - self._prev_network[1])
        # Rebase after a gap rather than assigning several intervals to one sample.
        self._prev_network = current_network

        top_name: str | None = None
        top_pid: int | None = None
        top_cpu: float | None = None
        top_mem: float | None = None
        top_count: int | None = None
        top_cgroup: str | None = None
        if cpu_pct >= 75.0 or mem_pct >= 75.0:
            if mem_pct >= 75.0 and (cpu_pct < 75.0 or mem_pct >= cpu_pct):
                focus_metric: Literal["auto", "cpu", "memory"] = "memory"
            else:
                focus_metric = "cpu"
            top_name, top_pid, top_cpu, top_mem, top_count, top_cgroup = self._find_top_process(
                focus_metric=focus_metric,
                normalize_cpu=True,
            )

        return MetricSample(
            observed_at=datetime.now(UTC),
            cpu_percent=round(cpu_pct, 2),
            memory_percent=round(mem_pct, 2),
            disk_percent=round(disk_pct, 2) if disk_pct is not None else None,
            network_rx_bytes=rx_delta,
            network_tx_bytes=tx_delta,
            top_process_name=top_name,
            top_process_pid=top_pid,
            top_process_cpu_percent=top_cpu,
            top_process_memory_percent=top_mem,
            top_process_count=top_count,
            top_process_cgroup=top_cgroup,
        )
