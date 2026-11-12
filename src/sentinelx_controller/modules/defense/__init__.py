"""Defense module for SentinelX Controller."""

from sentinelx_controller.modules.defense.models import DefenseActionModel
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.defense.service import DefenseService

__all__ = ["DefenseActionModel", "DefenseRepository", "DefenseService"]
