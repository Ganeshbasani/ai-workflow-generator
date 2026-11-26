"""Project lifecycle service tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fakes import sample_project, sample_result
from workflow_ai.errors import InputValidationError
from workflow_ai.persistence import SqliteProjectRepository
from workflow_ai.services import ProjectService


@pytest.fixture()
def service(tmp_path: Path) -> ProjectService:
    return ProjectService(SqliteProjectRepository(tmp_path / "workflows.db"))


def test_create_from_result_stores_provenance(service: ProjectService) -> None:
    result = sample_result()
    project = service.create_from_result(
        result,
        owner_id="session-1",
        prompt="Process the order",
        category="Business Organizations",
    )

    loaded = service.load(project.id, "session-1")
    assert loaded.workflow.model_dump() == result.workflow.model_dump()
    assert loaded.metadata is not None
    assert loaded.metadata.category == "Business Organizations"
    assert loaded.metadata.prompt == "Process the order"
    assert loaded.metadata.provider == "rule"
    assert loaded.metadata.latency_ms == pytest.approx(12.5)


def test_list_and_load_are_session_scoped(service: ProjectService) -> None:
    one = service.create_from_result(
        sample_result(), owner_id="session-1", prompt="a", category="Business Organizations"
    )
    service.create_from_result(
        sample_result(), owner_id="session-2", prompt="b", category="Business Organizations"
    )

    assert [project.id for project in service.list_projects("session-1")] == [one.id]
    with pytest.raises(InputValidationError):
        service.load(one.id, "session-2")


def test_rename_is_bounded_and_scoped(service: ProjectService) -> None:
    project = service.create_from_result(
        sample_result(), owner_id="session-1", prompt="a", category="Business Organizations"
    )

    renamed = service.rename(project.id, "  My workflow  ", "session-1")
    assert renamed.display_title == "My workflow"
    assert service.load(project.id, "session-1").display_title == "My workflow"
    assert service.rename(project.id, "x" * 500, "session-1").title == "x" * 200

    with pytest.raises(InputValidationError, match="non-empty"):
        service.rename(project.id, "   ", "session-1")


def test_delete_scopes_to_owner(service: ProjectService) -> None:
    project = service.create_from_result(
        sample_result(), owner_id="session-1", prompt="a", category="Business Organizations"
    )

    assert service.delete(project.id, "session-2") is False
    assert service.delete(project.id, "session-1") is True
    assert service.list_projects("session-1") == []


def test_save_and_replace_workflow(service: ProjectService) -> None:
    project = sample_project("session-1")
    service.save(project)

    new_workflow = project.workflow.model_copy(update={"title": "Edited title"})
    updated = service.replace_workflow(project.id, new_workflow, "session-1")

    assert updated.workflow.title == "Edited title"
    assert service.load(project.id, "session-1").workflow.title == "Edited title"


def test_missing_project_raises_typed_error(service: ProjectService) -> None:
    with pytest.raises(InputValidationError, match="no longer exists"):
        service.load("prj_missing", "session-1")
