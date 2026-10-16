"""Unit tests for Backend and BackendPool in SentinelX Load Balancer."""

from sentinelx_lb.config import BackendConfig
from sentinelx_lb.pool import Backend, BackendPool


def test_backend_acquire_and_release_lifecycle() -> None:
    """Verify acquire increments in-flight and release updates outcomes properly."""
    b = Backend(url="http://10.0.1.1:8000", name="web-1")
    assert b.in_flight == 0
    assert b.total_requests == 0

    # Request 1 starts
    b.acquire()
    assert b.in_flight == 1
    assert b.total_requests == 1

    # Request 2 starts concurrently
    b.acquire()
    assert b.in_flight == 2
    assert b.total_requests == 2

    # Request 1 completes with 200 OK
    b.release(status_code=200)
    assert b.in_flight == 1
    assert b.success_requests == 1
    assert b.error_requests == 0

    # Request 2 completes with 500 Internal Error
    b.release(status_code=500)
    assert b.in_flight == 0
    assert b.success_requests == 1
    assert b.error_requests == 1

    # Redundant release must not drop below zero
    b.release(status_code=200)
    assert b.in_flight == 0


def test_backend_release_network_error() -> None:
    """Verify is_error=True increments error_requests even without status code."""
    b = Backend(url="http://10.0.1.1:8000", name="web-1")
    b.acquire()
    b.release(is_error=True)
    assert b.in_flight == 0
    assert b.error_requests == 1
    assert b.success_requests == 0


def test_backend_pool_from_configs_and_lookup() -> None:
    """Verify BackendPool initializes backends and supports URL lookup."""
    configs = [
        BackendConfig(url="http://10.0.1.10:8000", name="primary"),
        BackendConfig(url="http://10.0.1.20:8000/"),  # Tests trailing slash normalization
    ]
    pool = BackendPool.from_configs(configs)

    assert len(pool.backends) == 2
    assert pool.backends[0].name == "primary"
    assert pool.backends[1].name == "backend-2"

    found = pool.get_by_url("http://10.0.1.10:8000")
    assert found is not None
    assert found.name == "primary"

    not_found = pool.get_by_url("http://10.0.99.99:8000")
    assert not_found is None


def test_backend_pool_stats_aggregation() -> None:
    """Verify pool stats aggregate in-flight, total requests, and backend statuses."""
    b1 = Backend(
        url="http://b1:8000",
        name="b1",
        in_flight=2,
        total_requests=10,
        success_requests=9,
        error_requests=1,
    )
    b2 = Backend(
        url="http://b2:8000",
        name="b2",
        in_flight=0,
        total_requests=5,
        success_requests=5,
        error_requests=0,
        is_healthy=False,
    )
    pool = BackendPool(backends=[b1, b2])

    stats = pool.stats()
    assert stats["total_backends"] == 2
    assert stats["healthy_backends"] == 1
    assert stats["total_in_flight"] == 2
    assert stats["total_requests"] == 15
    assert stats["total_success"] == 14
    assert stats["total_errors"] == 1
    assert len(stats["backends"]) == 2
