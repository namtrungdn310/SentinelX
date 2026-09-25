"""Tests to check package setup."""

import sentinelx_agent
import sentinelx_common
import sentinelx_controller
import sentinelx_lb


def test_packages_importable() -> None:
    """Check that all packages can be imported and have versions."""
    assert sentinelx_common.__version__ == "0.1.0"
    assert sentinelx_controller.__version__ == "0.1.0"
    assert sentinelx_agent.__version__ == "0.1.0"
    assert sentinelx_lb.__version__ == "0.1.0"


def test_fixture_injection(sample_version: str) -> None:
    """Check that pytest fixtures work."""
    assert sample_version == "0.1.0"
