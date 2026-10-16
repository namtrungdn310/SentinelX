"""Load balancing distribution strategies for SentinelX."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sentinelx_lb.config import LBAlgorithm
from sentinelx_lb.pool import Backend, BackendPool


class RoutingStrategy(ABC):
    """Abstract base class for load balancing selection strategies."""

    @abstractmethod
    def select_backend(self, backends: Sequence[Backend]) -> Backend | None:
        """Select a backend from the given candidate list."""
        raise NotImplementedError


class RoundRobinStrategy(RoutingStrategy):
    """Distributes requests sequentially across available backends."""

    def __init__(self) -> None:
        self._index = 0

    def select_backend(self, backends: Sequence[Backend]) -> Backend | None:
        if not backends:
            return None

        chosen = backends[self._index % len(backends)]
        self._index = (self._index + 1) % len(backends)
        return chosen


class LeastInFlightStrategy(RoutingStrategy):
    """Routes requests to the backend with the lowest number of active (in-flight) requests."""

    def __init__(self) -> None:
        self._tie_breaker = 0

    def select_backend(self, backends: Sequence[Backend]) -> Backend | None:
        if not backends:
            return None

        # Find the minimum in_flight value among available backends
        min_in_flight = min(b.in_flight for b in backends)
        candidates = [b for b in backends if b.in_flight == min_in_flight]

        # Break ties evenly using round-robin among candidates with identical lowest load
        chosen = candidates[self._tie_breaker % len(candidates)]
        self._tie_breaker = (self._tie_breaker + 1) % len(candidates)
        return chosen


class LoadBalancer:
    """Core load balancer coordinating pool selection with dynamic strategy."""

    def __init__(
        self,
        pool: BackendPool,
        algorithm: LBAlgorithm = LBAlgorithm.ROUND_ROBIN,
    ) -> None:
        self.pool = pool
        self._algorithm = algorithm
        self._strategy: RoutingStrategy = self._create_strategy(algorithm)

    @property
    def algorithm(self) -> LBAlgorithm:
        """Return the active routing algorithm."""
        return self._algorithm

    def _create_strategy(self, algorithm: LBAlgorithm) -> RoutingStrategy:
        if algorithm == LBAlgorithm.LEAST_IN_FLIGHT:
            return LeastInFlightStrategy()
        return RoundRobinStrategy()

    def set_algorithm(self, algorithm: LBAlgorithm) -> None:
        """Switch routing algorithm dynamically at runtime."""
        self._algorithm = algorithm
        self._strategy = self._create_strategy(algorithm)

    def select_backend(self) -> Backend | None:
        """Select the next healthy backend from the pool."""
        available = self.pool.get_available_backends()
        return self._strategy.select_backend(available)
