"""Repositories package providing factory for backend selection."""

from typing import Optional, Union
import os

from config import get_config
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    KnowledgeRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    TelemetryRepository,
)
from repositories.memory.memory_repository import InMemoryRepository
from repositories.snowflake.connection import SnowflakeConnectionManager
from repositories.snowflake.snowflake_repository import SnowflakeRepository

_IN_MEMORY_INSTANCE: Optional[InMemoryRepository] = None


def get_repository(backend: Optional[str] = None) -> Union[InMemoryRepository, SnowflakeRepository]:
    """Return configured repository instance (in-memory singleton or Snowflake).

    Follows AGENT.md:
    - Never masquerades in-memory as Snowflake
    - Allows seamless offline execution and unit testing
    """
    global _IN_MEMORY_INSTANCE
    config = get_config()
    selected_backend = backend or config.storage_backend

    if selected_backend == "snowflake" and config.snowflake.is_configured:
        return SnowflakeRepository(SnowflakeConnectionManager(config.snowflake))

    if _IN_MEMORY_INSTANCE is None:
        _IN_MEMORY_INSTANCE = InMemoryRepository(seed=True)
    return _IN_MEMORY_INSTANCE


__all__ = [
    "get_repository",
    "MachineRepository",
    "TelemetryRepository",
    "MaintenanceRepository",
    "ReliabilityRepository",
    "InvestigationRepository",
    "GovernanceRepository",
    "KnowledgeRepository",
    "InMemoryRepository",
    "SnowflakeRepository",
    "SnowflakeConnectionManager",
]
