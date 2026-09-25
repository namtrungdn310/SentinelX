"""ID helper functions for SentinelX.
Generates and checks UUID v4 (generate random) strings for nodes, projects, and events.
"""

import uuid


def generate_id() -> str:
    """Create a new random UUID v4 string.
    Example output: '9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d'
    """
    return str(uuid.uuid4())


def is_valid_uuid(val: str) -> bool:
    """Check if a string is a valid UUID.
    Returns True if valid, False if not.
    """
    try:
        uuid_obj = uuid.UUID(val.strip())
        return str(uuid_obj) == val.strip().lower()

    except (ValueError, AttributeError):
        return False
