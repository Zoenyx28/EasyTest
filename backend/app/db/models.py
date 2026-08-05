"""SQLAlchemy ORM models for test execution history and discovery cache."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    """System user for authentication and authorization."""
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(512), default='')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    tags: Mapped[str] = mapped_column(String(1024), default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    test_type: Mapped[str] = mapped_column(String(16), default='api')
    file_path: Mapped[str] = mapped_column(String(512), default='')


# ── New Execution Model (Task + Execution + ExecutionCase) ──

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
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectMember(Base):
    """Association between project and user — project membership."""
    __tablename__ = 'project_members'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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


# ── Defect Management ──


class DefectModule(Base):
    """缺陷模块 - 项目级模块树"""
    __tablename__ = 'defect_modules'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Defect(Base):
    """缺陷记录"""
    __tablename__ = 'defects'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    steps: Mapped[str] = mapped_column(Text, default='')
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_id: Mapped[int] = mapped_column(Integer, nullable=False)
    module_id: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[str] = mapped_column(String(16), default='P3')
    priority: Mapped[str] = mapped_column(String(16), default='P3')
    status: Mapped[str] = mapped_column(String(32), default='unconfirmed')
    resolution: Mapped[str] = mapped_column(String(64), default='')
    assignee_id: Mapped[int] = mapped_column(Integer, default=0)
    creator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bug_type: Mapped[str] = mapped_column(String(32), default='code_error')
    deadline: Mapped[str] = mapped_column(String(32), default='')
    resolved_version: Mapped[int] = mapped_column(Integer, default=0)
    resolved_date: Mapped[str] = mapped_column(String(32), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DefectAttachment(Base):
    """缺陷附件"""
    __tablename__ = 'defect_attachments'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    filepath: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(64), default='')
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DefectLog(Base):
    """缺陷操作日志"""
    __tablename__ = 'defect_logs'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, default='')
    new_value: Mapped[str] = mapped_column(Text, default='')
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DefectComment(Base):
    """缺陷评论"""
    __tablename__ = 'defect_comments'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 支持Markdown/图片
    author_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
