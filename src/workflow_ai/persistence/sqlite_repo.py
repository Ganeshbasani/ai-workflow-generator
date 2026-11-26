"""SQLite-backed project repository with idempotent forward migration.

No ORM: Pydantic models remain the single source of truth. Rows store JSON
snapshots; SQLite supplies durable, transactional storage and owner scoping.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from ..models import Project

_SCHEMA_VERSION = 1

_PROJECTS_DDL = """
CREATE TABLE IF NOT EXISTS projects (
    id            TEXT PRIMARY KEY,
    owner_id      TEXT,
    title         TEXT NOT NULL,
    domain        TEXT NOT NULL,
    workflow_json TEXT NOT NULL,
    metadata_json TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
)
"""

_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id)",
)


class SqliteProjectRepository:
    """Store projects and their run history in a local SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = RLock()
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # One long-lived connection: required for ``:memory:`` databases (a new
        # connection would be a new, empty database) and cheaper for files.
        # Access is serialized by the reentrant lock; Streamlit may rerun on
        # multiple threads, so the connection must not enforce thread affinity.
        self._conn = sqlite3.connect(
            self.db_path, timeout=10, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.ensure_schema()

    def close(self) -> None:
        """Release the underlying connection. Safe to call more than once."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SqliteProjectRepository:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield the shared connection inside a serialized transaction."""
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def ensure_schema(self) -> None:
        """Create tables and apply any pending forward migrations.

        Safe to call on every startup: an existing schema is left untouched
        unless a known earlier version is detected.
        """
        with self._connect() as conn:
            conn.execute(_PROJECTS_DDL)
            conn.execute(_RUNS_DDL)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER NOT NULL)"
            )
            for statement in _INDEXES:
                conn.execute(statement)

            columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
            if "metadata_json" not in columns:
                conn.execute("ALTER TABLE projects ADD COLUMN metadata_json TEXT")

            row = conn.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_meta(version) VALUES (?)", (_SCHEMA_VERSION,))
            elif int(row["version"]) < _SCHEMA_VERSION:
                conn.execute(
                    "UPDATE schema_meta SET version = ?", (_SCHEMA_VERSION,)
                )

    def save(self, project: Project) -> None:
        """Insert or replace a project and its runs in one transaction."""
        project.touch()
        workflow_json = project.workflow.model_dump_json()
        metadata_json = (
            project.metadata.model_dump_json() if project.metadata else None
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects
                    (id, owner_id, title, domain, workflow_json, metadata_json,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    title = excluded.title,
                    domain = excluded.domain,
                    workflow_json = excluded.workflow_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    project.id,
                    project.owner_id,
                    project.title,
                    project.workflow.domain,
                    workflow_json,
                    metadata_json,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
            conn.execute("DELETE FROM runs WHERE project_id = ?", (project.id,))
            conn.executemany(
                "INSERT INTO runs (id, project_id, payload_json) VALUES (?, ?, ?)",
                [
                    (run.id, project.id, run.model_dump_json())
                    for run in project.runs
                ],
            )

    @staticmethod
    def _hydrate(
        conn: sqlite3.Connection, row: sqlite3.Row
    ) -> Project:
        run_rows = conn.execute(
            "SELECT payload_json FROM runs WHERE project_id = ? ORDER BY rowid",
            (row["id"],),
        ).fetchall()
        data = {
            "id": row["id"],
            "owner_id": row["owner_id"],
            "workflow": json.loads(row["workflow_json"]),
            "title": row["title"],
            "metadata": (
                json.loads(row["metadata_json"]) if row["metadata_json"] else None
            ),
            "runs": [json.loads(run["payload_json"]) for run in run_rows],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        return Project.model_validate(data)

    def get(self, project_id: str, owner_id: str | None) -> Project | None:
        """Return an owned project, or ``None`` when it does not exist."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ? AND owner_id IS ?",
                (project_id, owner_id),
            ).fetchone()
            return self._hydrate(conn, row) if row is not None else None

    def list(self, owner_id: str | None) -> list[Project]:
        """Return the owner's projects, most recently updated first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects WHERE owner_id IS ? "
                "ORDER BY updated_at DESC, id",
                (owner_id,),
            ).fetchall()
            return [self._hydrate(conn, row) for row in rows]

    def delete(self, project_id: str, owner_id: str | None) -> bool:
        """Delete an owned project; return whether a row was removed."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM projects WHERE id = ? AND owner_id IS ?",
                (project_id, owner_id),
            )
            return cursor.rowcount > 0
