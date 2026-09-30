"""Pytest test configuration and fixtures."""

import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from repositories.memory.memory_repository import InMemoryRepository


@pytest.fixture
def memory_repo() -> InMemoryRepository:
    """Fixture providing a fresh pre-seeded in-memory repository."""
    return InMemoryRepository(seed=True)


@pytest.fixture
def empty_memory_repo() -> InMemoryRepository:
    """Fixture providing an unseeded in-memory repository."""
    return InMemoryRepository(seed=False)
