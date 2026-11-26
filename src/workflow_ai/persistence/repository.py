"""Storage-agnostic persistence contract.

``owner_id`` is nullable now (anonymous, session-scoped projects) but is part
of every operation so an authenticated deployment can scope rows to a user
without changing callers. Implementations MUST treat ``None`` as a real scope
that matches only unowned rows.
"""

from __future__ import annotations

from typing import Protocol

from ..models import Project


class ProjectRepository(Protocol):
    """Persist and retrieve :class:`Project` aggregates."""

    def ensure_schema(self) -> None:
        """Create or migrate the underlying schema; must be idempotent."""
        ...

    def save(self, project: Project) -> None:
        """Insert or fully update a project (including its runs)."""
        ...

    def get(self, project_id: str, owner_id: str | None) -> Project | None:
        """Return one project scoped to its owner, or ``None``."""
        ...

    def list(self, owner_id: str | None) -> list[Project]:
        """Return the owner's projects, most recently updated first."""
        ...

    def delete(self, project_id: str, owner_id: str | None) -> bool:
        """Delete one project; return ``True`` when a row was removed."""
        ...
