"""Local agent identity management and persistence."""

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from sentinelx_common.contracts.base import SentinelXBaseModel
from sentinelx_common.utils.time import ensure_utc

logger = logging.getLogger("sentinelx_agent.identity")


class AgentIdentity(SentinelXBaseModel):
    """Local identity record stored on the agent host."""

    node_id: str
    agent_id: str
    status: str = "enrolled"
    enrolled_at: datetime


class AgentIdentityManager:
    """Load and persist agent identity credentials atomically."""

    @staticmethod
    def load(identity_path: Path) -> AgentIdentity | None:
        """Load agent identity from disk if present."""
        if not identity_path.is_file():
            logger.info("No existing identity file found at: %s", identity_path)
            return None

        try:
            with open(identity_path, encoding="utf-8") as f:
                raw_data = json.load(f)
            identity = AgentIdentity.model_validate(raw_data)
            logger.info(
                "Loaded local agent identity: node_id=%s, agent_id=%s",
                identity.node_id,
                identity.agent_id,
            )
            return identity
        except Exception as err:
            logger.warning(
                "Failed to parse existing identity file (%s). Will re-enroll: %s",
                identity_path,
                err,
            )
            return None

    @staticmethod
    def save(identity_path: Path, identity: AgentIdentity) -> None:
        """Save agent identity to disk atomically."""
        identity_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "node_id": identity.node_id,
            "agent_id": identity.agent_id,
            "status": identity.status,
            "enrolled_at": ensure_utc(identity.enrolled_at).isoformat(),
        }

        # Write to temporary file in the same folder, then atomic rename
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=identity_path.parent,
            delete=False,
            encoding="utf-8",
        )
        try:
            with temp_file as f:
                json.dump(data, f, indent=2)
            Path(temp_file.name).replace(identity_path)
            logger.info("Saved agent identity atomically to: %s", identity_path)
        except Exception:
            if Path(temp_file.name).exists():
                Path(temp_file.name).unlink()
            raise
