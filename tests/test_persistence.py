"""Repository tests: round-trip equality, owner scoping and schema migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tests.fakes import sample_project
from workflow_ai.persistence import SqliteProjectRepository


def test_round_trip_preserves_the_whole_aggregate(tmp_path: Path) -> None:
    repo = SqliteProjectRepository(tmp_path / "workflows.db")
    project = sample_project("session-1")

    repo.save(project)
    loaded = repo.get(project.id, "session-1")

    assert loaded is not None
    assert loaded.model_dump() == project.model_dump()
    assert loaded.workflow.model_dump() == project.workflow.model_dump()
    assert loaded.metadata is not None
    assert loaded.metadata.prompt == "Process the order. Invoice."


def test_owner_scoping_includes_null_owners(tmp_path: Path) -> None:
    repo = SqliteProjectRepository(tmp_path / "workflows.db")
    owned = sample_project("session-1")
    anonymous = sample_project()
    repo.save(owned)
    repo.save(anonymous)

    assert [project.id for project in repo.list("session-1")] == [owned.id]
    assert [project.id for project in repo.list(None)] == [anonymous.id]
    assert repo.get(owned.id, None) is None
    assert repo.get(anonymous.id, None) is not None


def test_delete_is_owner_scoped(tmp_path: Path) -> None:
    repo = SqliteProjectRepository(tmp_path / "workflows.db")
    project = sample_project("session-1")
    repo.save(project)

    assert repo.delete(project.id, "someone-else") is False
    assert repo.get(project.id, "session-1") is not None
    assert repo.delete(project.id, "session-1") is True
    assert repo.get(project.id, "session-1") is None
    assert repo.list("session-1") == []


def test_list_is_ordered_by_update_time(tmp_path: Path) -> None:
    repo = SqliteProjectRepository(tmp_path / "workflows.db")
    first = sample_project("session-1")
    second = sample_project("session-1")
    repo.save(first)
    repo.save(second)

    ordered = [project.id for project in repo.list("session-1")]
    assert set(ordered) == {first.id, second.id}
    assert ordered[0] == second.id  # saved last => most recently updated


def test_upsert_replaces_runs_without_duplicates(tmp_path: Path) -> None:
    from workflow_ai.models import RunRecord

    repo = SqliteProjectRepository(tmp_path / "workflows.db")
    project = sample_project()
    repo.save(project)

    project.runs.append(RunRecord(project_id=project.id, outcome="completed"))
    repo.save(project)
    loaded = repo.get(project.id, None)

    assert loaded is not None
    assert len(loaded.runs) == 1
    assert loaded.runs[0].outcome == "completed"


def test_ensure_schema_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "workflows.db"
    repo = SqliteProjectRepository(path)
    repo.ensure_schema()
    repo.ensure_schema()

    with sqlite3.connect(path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"projects", "runs", "schema_meta"} <= tables


def test_migration_adds_missing_metadata_column(tmp_path: Path) -> None:
    """A v0 database gains metadata_json without losing existing rows."""
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                owner_id TEXT,
                title TEXT NOT NULL,
                domain TEXT NOT NULL,
                workflow_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "prj_legacy",
                "session-1",
                "Legacy",
                "business",
                sample_project().workflow.model_dump_json(),
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )

    repo = SqliteProjectRepository(path)

    loaded = repo.get("prj_legacy", "session-1")
    assert loaded is not None
    assert loaded.metadata is None
    assert loaded.display_title == "Legacy"

    with sqlite3.connect(path) as conn:
        version = conn.execute("SELECT version FROM schema_meta").fetchone()[0]
    assert version == 1


def test_repository_protocol_is_satisfied() -> None:
    from workflow_ai.persistence import ProjectRepository

    repo: ProjectRepository = SqliteProjectRepository(":memory:")
    assert repo.list(None) == []
