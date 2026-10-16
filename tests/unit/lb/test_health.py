"""Unit tests for active health check state machine and flapping protection."""

from sentinelx_lb.pool import Backend, BackendHealthState


def test_health_failure_transitions_to_degraded_then_ejected() -> None:
    """Verify consecutive failures transition: HEALTHY -> DEGRADED -> UNHEALTHY (ejection)."""
    b = Backend(url="http://b1:8000", name="b1")
    assert b.is_healthy is True
    assert b.health_state.value == BackendHealthState.HEALTHY.value

    failure_threshold = 3

    # Failure 1: enters DEGRADED, remains serving traffic
    changed = b.record_health_failure(failure_threshold, error_msg="HTTP 500", status_code=500)
    assert changed is False
    assert b.is_healthy is True
    assert b.health_state.value == BackendHealthState.DEGRADED.value
    assert b.consecutive_failures == 1
    assert b.consecutive_successes == 0

    # Failure 2: stays DEGRADED
    changed = b.record_health_failure(failure_threshold, error_msg="HTTP 500", status_code=500)
    assert changed is False
    assert b.is_healthy is True
    assert b.health_state.value == BackendHealthState.DEGRADED.value
    assert b.consecutive_failures == 2

    # Failure 3: reaches threshold -> EJECTED (UNHEALTHY)
    changed = b.record_health_failure(failure_threshold, error_msg="HTTP 500", status_code=500)
    assert changed is True  # State changed to ejected
    assert b.is_healthy is False
    assert b.health_state.value == BackendHealthState.UNHEALTHY.value
    assert b.consecutive_failures == 3

    # Failure 4: stays UNHEALTHY, no new state change returned
    changed = b.record_health_failure(failure_threshold, error_msg="HTTP 500", status_code=500)
    assert changed is False
    assert b.is_healthy is False
    assert b.health_state.value == BackendHealthState.UNHEALTHY.value


def test_health_success_transitions_to_recovering_then_readded() -> None:
    """Verify consecutive successes transition: UNHEALTHY -> RECOVERING -> HEALTHY (re-add)."""
    b = Backend(
        url="http://b1:8000",
        name="b1",
        is_healthy=False,
        health_state=BackendHealthState.UNHEALTHY,
    )
    success_threshold = 2

    # Success 1: enters RECOVERING, not yet serving traffic
    changed = b.record_health_success(success_threshold, status_code=200)
    assert changed is False
    assert b.is_healthy is False
    assert b.health_state.value == BackendHealthState.RECOVERING.value
    assert b.consecutive_successes == 1
    assert b.consecutive_failures == 0

    # Success 2: reaches threshold -> RE-ADDED (HEALTHY)
    changed = b.record_health_success(success_threshold, status_code=200)
    assert changed is True  # State changed to re-added
    assert b.is_healthy is True
    assert b.health_state.value == BackendHealthState.HEALTHY.value
    assert b.consecutive_successes == 2


def test_intermittent_success_resets_failure_counter() -> None:
    """Verify a single success resets the failure count and recovers degraded state."""
    b = Backend(url="http://b1:8000", name="b1")
    failure_threshold = 3
    success_threshold = 2

    # 2 failures -> DEGRADED
    b.record_health_failure(failure_threshold, error_msg="Timeout")
    b.record_health_failure(failure_threshold, error_msg="Timeout")
    assert b.consecutive_failures == 2
    assert b.health_state.value == BackendHealthState.DEGRADED.value

    # 1 success -> resets failure count to 0
    b.record_health_success(success_threshold, status_code=200)
    assert b.consecutive_failures == 0
    assert b.consecutive_successes == 1

    # Another success -> back to HEALTHY
    b.record_health_success(success_threshold, status_code=200)
    assert b.health_state.value == BackendHealthState.HEALTHY.value
    assert b.is_healthy is True


def test_flapping_protection_baseline() -> None:
    """Verify repeated flip-flops trigger flapping flag and double the recovery threshold."""
    b = Backend(url="http://b1:8000", name="b1")
    failure_thresh = 1
    success_thresh = 1

    # Transition 1: UP -> DOWN
    b.record_health_failure(failure_thresh, "err")
    # Transition 2: DOWN -> UP
    b.record_health_success(success_thresh, 200)
    # Transition 3: UP -> DOWN
    b.record_health_failure(failure_thresh, "err")
    # Transition 4: DOWN -> UP (triggers flapping >= 4 transitions)
    b.record_health_success(success_thresh, 200)

    # Transition 5: UP -> DOWN
    b.record_health_failure(failure_thresh, "err")
    assert b.flapping_detected is True
    assert b.is_healthy is False

    # Because flapping_detected is True, effective threshold is 1 * 2 = 2
    # 1st success -> still recovering, not re-added
    re_added = b.record_health_success(success_thresh, 200)
    assert re_added is False
    assert b.is_healthy is False

    # 2nd success -> now re-added
    re_added = b.record_health_success(success_thresh, 200)
    assert re_added is True
    assert b.is_healthy is True
