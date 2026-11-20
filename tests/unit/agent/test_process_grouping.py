"""Unit tests for Agent Hybrid Process Grouping (Cgroup + Regex / PPID)."""

from unittest.mock import MagicMock, mock_open, patch

from sentinelx_agent.collectors.real import RealResourceCollector


def test_read_cgroup_service_success() -> None:
    cgroup_data = "0::/system.slice/celery-worker.service\n"
    with patch("builtins.open", mock_open(read_data=cgroup_data)):
        svc = RealResourceCollector._read_cgroup_service(1234)
        assert svc == "celery-worker.service"


def test_read_cgroup_service_missing() -> None:
    cgroup_data = "0::/user.slice/user-1000.slice/session-2.scope\n"
    with patch("builtins.open", mock_open(read_data=cgroup_data)):
        svc = RealResourceCollector._read_cgroup_service(1234)
        assert svc is None


def test_normalize_name_fallback_regex() -> None:
    # 1. Trailing worker index / number removal
    assert RealResourceCollector._normalize_name_fallback("celery-worker-1") == "celery-worker"
    assert RealResourceCollector._normalize_name_fallback("celery-worker_2") == "celery-worker"
    assert RealResourceCollector._normalize_name_fallback("worker03") == "worker"
    assert (
        RealResourceCollector._normalize_name_fallback("gunicorn: worker [1]")
        == "gunicorn: worker"
    )

    # 2. Runtime wrapper command line inspection
    assert (
        RealResourceCollector._normalize_name_fallback(
            "python", ["python3", "-m", "celery", "worker"]
        )
        == "celery"
    )
    assert (
        RealResourceCollector._normalize_name_fallback(
            "node", ["node", "/app/server.js"]
        )
        == "server"
    )


def test_find_top_process_aggregates_group() -> None:
    # Mock psutil processes: 3 celery workers (each 25% CPU) and 1 snapd (10% CPU)
    proc1 = MagicMock()
    proc1.info = {
        "pid": 101,
        "name": "celery-worker-1",
        "cpu_percent": 25.0,
        "memory_percent": 10.0,
        "cmdline": [],
    }

    proc2 = MagicMock()
    proc2.info = {
        "pid": 102,
        "name": "celery-worker-2",
        "cpu_percent": 25.0,
        "memory_percent": 10.0,
        "cmdline": [],
    }

    proc3 = MagicMock()
    proc3.info = {
        "pid": 103,
        "name": "celery-worker-3",
        "cpu_percent": 25.0,
        "memory_percent": 10.0,
        "cmdline": [],
    }

    proc4 = MagicMock()
    proc4.info = {
        "pid": 201,
        "name": "snapd",
        "cpu_percent": 10.0,
        "memory_percent": 5.0,
        "cmdline": [],
    }

    with patch("psutil.process_iter", return_value=[proc1, proc2, proc3, proc4]), patch.object(
        RealResourceCollector, "_read_cgroup_service", return_value=None
    ):
        name, pid, cpu, mem, count, cgroup = RealResourceCollector._find_top_process()
        # Should group celery-worker-1, 2, 3 into "celery-worker" with 75% CPU, 30% RAM and count=3
        assert name == "celery-worker"
        assert pid == 101
        assert cpu == 75.0
        assert mem == 30.0
        assert count == 3
        assert cgroup is None


def test_find_top_process_priority_cgroup() -> None:
    proc1 = MagicMock()
    proc1.info = {
        "pid": 501,
        "name": "python",
        "cpu_percent": 40.0,
        "memory_percent": 10.0,
        "cmdline": ["python", "app.py"],
    }

    proc2 = MagicMock()
    proc2.info = {
        "pid": 502,
        "name": "python",
        "cpu_percent": 45.0,
        "memory_percent": 10.0,
        "cmdline": ["python", "app.py"],
    }

    with patch("psutil.process_iter", return_value=[proc1, proc2]), patch.object(
        RealResourceCollector, "_read_cgroup_service", return_value="celery.service"
    ):
        name, pid, cpu, mem, count, cgroup = RealResourceCollector._find_top_process()
        assert name == "celery"
        assert pid == 501
        assert cpu == 85.0
        assert mem == 20.0
        assert count == 2
        assert cgroup == "celery.service"


def test_find_top_process_memory_leak_dominant() -> None:
    # Process with low CPU (2%) but high RAM (65%)
    proc_leak = MagicMock()
    proc_leak.info = {
        "pid": 801,
        "name": "java",
        "cpu_percent": 2.0,
        "memory_percent": 65.0,
        "cmdline": ["java", "-jar", "app.jar"],
    }
    proc_normal = MagicMock()
    proc_normal.info = {
        "pid": 802,
        "name": "nginx",
        "cpu_percent": 15.0,
        "memory_percent": 5.0,
        "cmdline": [],
    }

    with patch("psutil.process_iter", return_value=[proc_leak, proc_normal]), patch.object(
        RealResourceCollector, "_read_cgroup_service", return_value=None
    ):
        name, pid, cpu, mem, count, cgroup = RealResourceCollector._find_top_process()
        assert name == "app"
        assert pid == 801
        assert cpu == 2.0
        assert mem == 65.0
        assert count == 1
