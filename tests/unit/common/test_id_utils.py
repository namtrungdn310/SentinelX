"""Tests for ID helper functions."""

from sentinelx_common.utils.ids import generate_id, is_valid_uuid


def test_generate_id_format() -> None:
    """Test that generate_id returns a valid 36-character UUID string."""
    id1 = generate_id()
    assert len(id1) == 36
    assert is_valid_uuid(id1) is True


def test_generate_id_unique() -> None:
    """Test that generate_id generates unique values."""
    id1 = generate_id()
    id2 = generate_id()
    assert id1 != id2


def test_is_valid_uuid_true() -> None:
    """Test that is_valid_uuid returns True for valid UUIDs."""
    valid_uuid = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
    assert is_valid_uuid(valid_uuid) is True
    # Test uppercase and spaces
    assert is_valid_uuid("  " + valid_uuid.upper() + "  ") is True


def test_is_valid_uuid_false() -> None:
    """Test that is_valid_uuid returns False for invalid strings."""
    assert is_valid_uuid("") is False
    assert is_valid_uuid("invalid-uuid") is False
    assert is_valid_uuid("12345") is False
    # Wrong character count
    assert is_valid_uuid("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6") is False
