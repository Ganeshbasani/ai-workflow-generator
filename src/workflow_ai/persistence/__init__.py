"""Persistence layer — repository interface and SQLite implementation."""

from .repository import ProjectRepository
from .sqlite_repo import SqliteProjectRepository

__all__ = ["ProjectRepository", "SqliteProjectRepository"]
