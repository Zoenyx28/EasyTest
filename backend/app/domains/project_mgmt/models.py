"""Project Management domain models — Project, Branch, membership."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, String, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class Branch(Base):
    """A named version/line-of-work within a Project — data isolation boundary."""
    __tablename__ = 'branches'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_branch_id: Mapped[int | None] = mapped_column(Integer, default=None)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_empty: Mapped[bool] = mapped_column(Boolean, default=False)
    source_path: Mapped[str] = mapped_column(String(1024), default='')
    test_path: Mapped[str] = mapped_column(String(512), default='')
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class Project(Base):
    """Test project definition — a source directory for test cases."""
    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), default='upload')
    server_path: Mapped[str] = mapped_column(String(1024), default='')
    test_path: Mapped[str] = mapped_column(String(512), default='')
    report_output: Mapped[str] = mapped_column(String(512), default='')
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    new_case_count: Mapped[int] = mapped_column(Integer, default=0)
    creator_id: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ProjectCase(Base):
    """Association between project and test case uid with status."""
    __tablename__ = 'project_cases'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False, name='case_uid')
    status: Mapped[str] = mapped_column(String(16), default='active')


class ProjectNote(Base):
    """Project-scoped Markdown note — one note per project (upsert)."""
    __tablename__ = 'project_notes'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, default='')
    updated_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectMember(Base):
    """Association between project and user — project membership."""
    __tablename__ = 'project_members'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserActiveProject(Base):
    """Per-user active project — each user activates a project independently."""
    __tablename__ = 'user_active_projects'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
