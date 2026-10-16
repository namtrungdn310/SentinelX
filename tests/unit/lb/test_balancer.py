"""Unit tests for Load Balancer distribution algorithms."""

from sentinelx_lb.balancer import LeastInFlightStrategy, LoadBalancer, RoundRobinStrategy
from sentinelx_lb.config import BackendConfig, LBAlgorithm
from sentinelx_lb.pool import Backend, BackendPool


def test_round_robin_strategy_sequential_rotation() -> None:
    """Verify Round Robin rotates evenly across backends and loops with modulo."""
    b1 = Backend(url="http://b1:8000", name="b1")
    b2 = Backend(url="http://b2:8000", name="b2")
    b3 = Backend(url="http://b3:8000", name="b3")
    backends = [b1, b2, b3]

    strategy = RoundRobinStrategy()

    # Sequence should cycle: b1 -> b2 -> b3 -> b1 -> b2
    assert strategy.select_backend(backends) == b1
    assert strategy.select_backend(backends) == b2
    assert strategy.select_backend(backends) == b3
    assert strategy.select_backend(backends) == b1
    assert strategy.select_backend(backends) == b2


def test_round_robin_strategy_empty_list() -> None:
    """Verify Round Robin returns None when candidate list is empty."""
    strategy = RoundRobinStrategy()
    assert strategy.select_backend([]) is None


def test_least_in_flight_strategy_selects_minimum_load() -> None:
    """Verify Least In-Flight picks the backend with lowest in_flight count."""
    b1 = Backend(url="http://b1:8000", name="b1", in_flight=5)
    b2 = Backend(url="http://b2:8000", name="b2", in_flight=1)  # Lowest
    b3 = Backend(url="http://b3:8000", name="b3", in_flight=3)
    backends = [b1, b2, b3]

    strategy = LeastInFlightStrategy()
    assert strategy.select_backend(backends) == b2


def test_least_in_flight_strategy_tie_breaker_rotation() -> None:
    """Verify Least In-Flight breaks ties evenly among candidates with equal lowest load."""
    b1 = Backend(url="http://b1:8000", name="b1", in_flight=0)
    b2 = Backend(url="http://b2:8000", name="b2", in_flight=0)
    b3 = Backend(url="http://b3:8000", name="b3", in_flight=2)
    backends = [b1, b2, b3]

    strategy = LeastInFlightStrategy()

    # b1 and b2 both have 0 in_flight. Tie breaker should cycle between b1 and b2.
    assert strategy.select_backend(backends) == b1
    assert strategy.select_backend(backends) == b2
    assert strategy.select_backend(backends) == b1


def test_least_in_flight_strategy_empty_list() -> None:
    """Verify Least In-Flight returns None when candidate list is empty."""
    strategy = LeastInFlightStrategy()
    assert strategy.select_backend([]) is None


def test_load_balancer_filters_unhealthy_backends() -> None:
    """Verify LoadBalancer only routes to healthy backends."""
    pool = BackendPool.from_configs([
        BackendConfig(url="http://b1:8000"),
        BackendConfig(url="http://b2:8000"),
    ])
    lb = LoadBalancer(pool=pool, algorithm=LBAlgorithm.ROUND_ROBIN)

    # Both healthy initially
    assert lb.select_backend() == pool.backends[0]
    assert lb.select_backend() == pool.backends[1]

    # Eject backend 0
    pool.backends[0].is_healthy = False
    assert lb.select_backend() == pool.backends[1]
    assert lb.select_backend() == pool.backends[1]


def test_load_balancer_runtime_algorithm_switch() -> None:
    """Verify algorithm can be toggled dynamically at runtime."""
    b1 = Backend(url="http://b1:8000", name="b1", in_flight=10)
    b2 = Backend(url="http://b2:8000", name="b2", in_flight=1)
    pool = BackendPool(backends=[b1, b2])

    lb = LoadBalancer(pool=pool, algorithm=LBAlgorithm.ROUND_ROBIN)
    assert lb.algorithm == LBAlgorithm.ROUND_ROBIN

    # Under Round Robin, first select returns b1
    assert lb.select_backend() == b1

    # Switch to Least In-Flight -> must choose b2 (in_flight=1)
    lb.set_algorithm(LBAlgorithm.LEAST_IN_FLIGHT)
    assert lb.algorithm.value == "least_in_flight"
    assert lb.select_backend() == b2
