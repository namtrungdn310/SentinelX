"""Common test fixtures for SentinelX."""

import pytest


@pytest.fixture
def sample_version() -> str:
    """Return expected initial version."""
    return "0.1.0"
