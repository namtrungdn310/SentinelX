"""Bootstrap and package skeleton unit tests."""

import sentinelx_agent
import sentinelx_common
import sentinelx_controller
import sentinelx_lb


def test_packages_importable() -> None:
    """Verify that all 4 runtime/shared packages are importable and have version strings."""
    assert sentinelx_common.__version__ == "0.1.0"
    assert sentinelx_controller.__version__ == "0.1.0"
    assert sentinelx_agent.__version__ == "0.1.0"
    assert sentinelx_lb.__version__ == "0.1.0"


def test_fixture_injection(sample_version: str) -> None:
    """Verify that pytest fixture injection functions correctly."""
    assert sample_version == "0.1.0"
