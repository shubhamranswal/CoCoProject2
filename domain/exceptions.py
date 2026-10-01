"""Typed operational domain exceptions for Factory Reliability Command Center.

Follows AGENT.md:
- Replaces generic ValueError / Exception with explicit domain errors
- Preserves security: never leaks credentials or internal implementation details
- Surfaces clear, actionable context for operator interfaces
"""

from __future__ import annotations


class CommandCenterError(Exception):
    """Base exception for all Factory Reliability Command Center errors."""

    def __init__(self, message: str, entity_id: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.entity_id = entity_id


DomainError = CommandCenterError


class ApprovalRequiredError(CommandCenterError, PermissionError):
    """Raised when an action is attempted without an approved Human Approval record."""


class ApprovalExpiredError(CommandCenterError, ValueError):
    """Raised when an action is attempted using an expired approval request."""


class InvalidWorkOrderTransitionError(CommandCenterError, ValueError):
    """Raised when a work order lifecycle state jump violates the state machine."""


class VerificationNotReadyError(CommandCenterError, ValueError):
    """Raised when physical verification is attempted before maintenance is COMPLETED."""


class RepositoryUnavailableError(CommandCenterError, RuntimeError):
    """Raised when the selected storage backend (e.g. Snowflake) cannot be reached."""


class InvalidMachineError(CommandCenterError, ValueError):
    """Raised when an operation targets an unknown or invalid machine identifier."""


class DuplicateActionError(CommandCenterError, ValueError):
    """Raised when a non-idempotent duplicate action execution is detected."""


class ValidationError(CommandCenterError, ValueError):
    """Raised when structured input/output validation fails."""


class ResourceNotFoundError(CommandCenterError, KeyError):
    """Raised when a requested resource does not exist."""
