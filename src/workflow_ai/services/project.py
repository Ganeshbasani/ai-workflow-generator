"""Project lifecycle service: save, list, load, rename and delete."""

from __future__ import annotations

import logging

from ..errors import InputValidationError
from ..logging_config import get_logger
from ..models import (
    GenerationMetadata,
    GenerationResult,
    Project,
    Workflow,
)
from ..persistence import ProjectRepository


class ProjectService:
    """Own project persistence and ownership scoping."""

    def __init__(
        self,
        repository: ProjectRepository,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._logger = logger or get_logger(__name__)
        self._repository.ensure_schema()

    def create_from_result(
        self,
        result: GenerationResult,
        *,
        owner_id: str | None,
        prompt: str,
        category: str,
    ) -> Project:
        """Persist a generation result as a new owned project."""
        project = Project(
            owner_id=owner_id,
            workflow=result.workflow,
            metadata=GenerationMetadata.from_result(
                result, category=category, prompt=prompt
            ),
        )
        self.save(project)
        self._logger.info(
            "project.created id=%s owner=%s steps=%d provider=%s",
            project.id,
            "session" if owner_id else "anonymous",
            len(project.workflow.steps),
            result.provider,
        )
        return project

    def save(self, project: Project) -> Project:
        """Persist the whole aggregate (used by editing and run services)."""
        self._repository.save(project)
        return project

    def list_projects(self, owner_id: str | None) -> list[Project]:
        """Return the owner's saved projects, newest first."""
        return self._repository.list(owner_id)

    def load(self, project_id: str, owner_id: str | None) -> Project:
        """Load a project or raise a user-safe typed error."""
        project = self._repository.get(project_id, owner_id)
        if project is None:
            raise InputValidationError("The selected workflow no longer exists.")
        return project

    def rename(self, project_id: str, new_title: str, owner_id: str | None) -> Project:
        """Rename a project with a non-empty display title."""
        title = new_title.strip()
        if not title:
            raise InputValidationError("Please enter a non-empty name.")
        project = self.load(project_id, owner_id)
        project.title = title[:200]
        return self.save(project)

    def replace_workflow(
        self, project_id: str, workflow: Workflow, owner_id: str | None
    ) -> Project:
        """Store a re-validated workflow (called only by the editor)."""
        project = self.load(project_id, owner_id)
        project.workflow = workflow
        return self.save(project)

    def delete(self, project_id: str, owner_id: str | None) -> bool:
        """Delete a project scoped to its owner; return whether it existed."""
        deleted = self._repository.delete(project_id, owner_id)
        if deleted:
            self._logger.info("project.deleted id=%s", project_id)
        return deleted
