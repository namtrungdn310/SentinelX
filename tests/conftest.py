"""Pytest configuration and global fixtures for SentinelX test suite."""

import pytest


@pytest.fixture
def sample_version() -> str:
    """Fixture returning the expected initial package version."""
    return "0.1.0"
