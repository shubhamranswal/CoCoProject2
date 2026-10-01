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

from domain.exceptions import RepositoryUnavailableError

_IN_MEMORY_INSTANCE: Optional[InMemoryRepository] = None


def get_repository(backend: Optional[str] = None) -> Union[InMemoryRepository, SnowflakeRepository]:
    """Return configured repository instance (in-memory singleton or Snowflake).

    Follows AGENT.md:
    - Never masquerades in-memory as Snowflake
    - Explicit failure: if Snowflake is requested and unavailable, raises RepositoryUnavailableError
    - Allows seamless offline execution and unit testing via in-memory backend
    """
    global _IN_MEMORY_INSTANCE
    config = get_config()
    selected_backend = (backend or config.storage_backend).lower()

    if selected_backend == "snowflake":
        if not config.snowflake.is_configured:
            raise RepositoryUnavailableError(
                "Snowflake backend requested, but credentials are not configured in environment."
            )
        conn_mgr = SnowflakeConnectionManager(config.snowflake)
        ok, msg = conn_mgr.test_connection()
        if not ok:
            raise RepositoryUnavailableError(f"Snowflake backend requested, but connection failed: {msg}")
        return SnowflakeRepository(conn_mgr)

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
