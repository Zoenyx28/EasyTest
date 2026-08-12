"""Test Execution domain models — discovery cache, tasks, executions, reports."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class TestCaseDefinition(Base):
    """Persistent cache of pytest discovery results, keyed by (uid, project_id, branch_id)."""
    __tablename__ = 'test_case_definitions'

    uid: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), default='')
    method_name: Mapped[str] = mapped_column(String(256), default='')
    class_name: Mapped[str] = mapped_column(String(256), default='')
    module: Mapped[str] = mapped_column(String(128), default='')
    full_name: Mapped[str] = mapped_column(String(512), default='')
    description: Mapped[str] = mapped_column(Text, default='')
    steps: Mapped[str] = mapped_column(Text, default='')
    tags: Mapped[str] = mapped_column(String(1024), default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    test_type: Mapped[str] = mapped_column(String(16), default='api')
    file_path: Mapped[str] = mapped_column(String(512), default='')


class Task(Base):
    """Test task definition — a named collection of test cases."""
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    status: Mapped[str] = mapped_column(String(32), default='pending')
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskCase(Base):
    """Association between task and test case uid."""
    __tablename__ = 'task_cases'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Execution(Base):
    """An execution instance of a test task."""
    __tablename__ = 'executions'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    task_name: Mapped[str] = mapped_column(String(255), default='')
    status: Mapped[str] = mapped_column(String(32), default='waiting')
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, default=0)
    running_count: Mapped[int] = mapped_column(Integer, default=0)
    waiting_count: Mapped[int] = mapped_column(Integer, default=0)
    concurrency: Mapped[int] = mapped_column(Integer, default=2)
    sequential: Mapped[bool] = mapped_column(Boolean, default=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class ExecutionCase(Base):
    """Per-case status during an execution — the core tracking table."""
    __tablename__ = 'execution_cases'
    __table_args__ = (
        Index('idx_ec_execution_id', 'execution_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(16), nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    case_name: Mapped[str] = mapped_column(String(500), default='')
    description: Mapped[str] = mapped_column(Text, default='')
    method_name: Mapped[str] = mapped_column(String(255), default='')
    class_name: Mapped[str] = mapped_column(String(255), default='')
    module: Mapped[str] = mapped_column(String(255), default='')
    status: Mapped[str] = mapped_column(String(32), default='waiting')
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, default=None)
    trace: Mapped[str | None] = mapped_column(Text, default=None)
    logs: Mapped[str | None] = mapped_column(Text, default=None)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    test_type: Mapped[str] = mapped_column(String(16), default='api')
    steps: Mapped[str | None] = mapped_column(Text, default=None)
    screenshots: Mapped[str | None] = mapped_column(Text, default=None)


class Report(Base):
    """Test report stored in database, replacing history.json."""
    __tablename__ = 'reports'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    module_groups: Mapped[str | None] = mapped_column(Text, default=None)
    results: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
