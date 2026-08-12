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
    steps: Mapped[str] = mapped_column(Text, default='')  # JSON string of test steps
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


class UserActiveProject(Base):
    """Per-user active project — each user activates a project independently."""
    __tablename__ = 'user_active_projects'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    """缺陷模块 - 项目级+版本级模块树"""
    __tablename__ = 'defect_modules'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
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
    case_uid: Mapped[str] = mapped_column(String(256), default='')
    case_name: Mapped[str] = mapped_column(String(512), default='')
    # ADR-0016: 缺陷追溯需求
    requirement_id: Mapped[int] = mapped_column(Integer, default=0)
    bug_type: Mapped[str] = mapped_column(String(32), default='code_error')
    deadline: Mapped[str] = mapped_column(String(32), default='')
    resolved_version: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_defect_id: Mapped[int] = mapped_column(Integer, default=0)
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


# ── Requirement Management ──


class Requirement(Base):
    """需求记录 — 按 (project_id, branch_id) 隔离。

    状态机：pending_review → review_passed → story_confirmed → cases_generated → done
    任一步可「重新评审」：携带人工评论重调当前步智能体，直接覆盖输出。
    """
    __tablename__ = 'requirements'
    __table_args__ = (
        Index('idx_req_project_branch', 'project_id', 'branch_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default='')

    # ADR-0016: 来源信息嵌入（替代独立 requirement_sources 表）
    content: Mapped[str] = mapped_column(Text, default='')
    source_type: Mapped[str] = mapped_column(String(16), default='text')
    source_meta: Mapped[str] = mapped_column(Text, default='')

    priority: Mapped[str] = mapped_column(String(16), default='P2')
    status: Mapped[str] = mapped_column(String(32), default='pending_review')
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RequirementSource(Base):
    """需求来源 — 飞书链接或离线文件（txt/json/md/doc/docx/pdf/图片）。"""
    __tablename__ = 'requirement_sources'
    __table_args__ = (
        Index('idx_rs_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(16), default='lark_link')  # lark_link | file
    link: Mapped[str] = mapped_column(String(1024), default='')
    text_content: Mapped[str] = mapped_column(Text(length=2**24), default='')  # 提取/粘贴的正文（MySQL 映射 MEDIUMTEXT）
    filename: Mapped[str] = mapped_column(String(256), default='')
    filepath: Mapped[str] = mapped_column(String(512), default='')
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(64), default='')
    extracted: Mapped[bool] = mapped_column(Boolean, default=False)  # 飞书正文是否提取成功
    extract_error: Mapped[str] = mapped_column(Text, default='')  # 提取失败原因（未授权/无权限/非文档等）
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RequirementReview(Base):
    """需求评审结果 — 每次评审/重新评审覆盖写入，携带 AI 评分。"""
    __tablename__ = 'requirement_reviews'
    __table_args__ = (
        Index('idx_rr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, default='')          # 评审结论
    risks: Mapped[str] = mapped_column(Text, default='')               # JSON 数组字符串
    issues: Mapped[str] = mapped_column(Text, default='')              # JSON 数组字符串
    score: Mapped[int] = mapped_column(Integer, default=0)             # 100 分制
    score_reason: Mapped[str] = mapped_column(Text, default='')        # 评分原因
    review_comment: Mapped[str] = mapped_column(Text, default='')      # 人工补充评论
    gate_status: Mapped[str] = mapped_column(String(16), default='')   # PASS/WARNING/BLOCKED
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Story(Base):
    """Story 拆解结果 — 属于某需求，AI 评分随输出存储。"""
    __tablename__ = 'stories'
    __table_args__ = (
        Index('idx_story_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    acceptance_criteria: Mapped[str] = mapped_column(Text, default='')  # JSON 数组字符串
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_reason: Mapped[str] = mapped_column(Text, default='')
    dimension_scores: Mapped[str] = mapped_column(Text, default='')     # JSON：7 维评分（PRD V2.0 StoryReview）
    gate_status: Mapped[str] = mapped_column(String(16), default='')    # PASS/WARNING/BLOCKED
    dependencies: Mapped[str] = mapped_column(Text, default='')         # JSON：依赖 Story ID 列表
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GeneratedCase(Base):
    """智能体生成的测试用例 — 可绑定自动化用例。"""
    __tablename__ = 'generated_cases'
    __table_args__ = (
        Index('idx_gc_requirement_id', 'requirement_id'),
        Index('idx_gc_story_id', 'story_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    story_id: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    preconditions: Mapped[str] = mapped_column(Text, default='')
    steps: Mapped[str] = mapped_column(Text, default='')                # JSON 数组字符串
    expected: Mapped[str] = mapped_column(Text, default='')
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_reason: Mapped[str] = mapped_column(Text, default='')
    gate_status: Mapped[str] = mapped_column(String(16), default='')    # PASS/WARNING/BLOCKED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CaseBinding(Base):
    """生成用例 ↔ 自动化用例（TestCaseDefinition 复合主键）0..N 绑定。"""
    __tablename__ = 'case_bindings'
    __table_args__ = (
        Index('idx_cb_generated_case_id', 'generated_case_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    generated_case_id: Mapped[int] = mapped_column(Integer, nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LLMSettings(Base):
    """LLM 全局配置（单行）— 登录用户可改，API key 仅存后端。"""
    __tablename__ = 'llm_settings'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), default='deepseek')
    api_base: Mapped[str] = mapped_column(String(512), default='')
    text_model: Mapped[str] = mapped_column(String(128), default='')
    vision_model: Mapped[str] = mapped_column(String(128), default='')
    api_key: Mapped[str] = mapped_column(String(512), default='')
    updated_by: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserLarkBinding(Base):
    """每用户飞书授权绑定 — token 生命周期由 lark-cli 管理。"""
    __tablename__ = 'user_lark_bindings'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    app_id: Mapped[str] = mapped_column(String(64), default='')
    lark_open_id: Mapped[str] = mapped_column(String(128), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ══════════════════════════════════════════════════════════
# PRD V2.0 分层测试设计模型（#20）
# ══════════════════════════════════════════════════════════


class RequirementAnalysis(Base):
    """需求分析 — AI 对需求的理解输出（先理解再测试），识别业务要素与信息缺口。"""
    __tablename__ = 'requirement_analyses'
    __table_args__ = (
        Index('idx_ra_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    elements: Mapped[str] = mapped_column(Text, default='')  # JSON：业务目标/角色/实体/流程/规则/状态/输入输出/异常/权限/依赖/风险
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_reason: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InformationGap(Base):
    """信息缺口 — 需求信息不足时创建，需产品确认。"""
    __tablename__ = 'information_gaps'
    __table_args__ = (
        Index('idx_ig_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    story_id: Mapped[int] = mapped_column(Integer, default=0)
    project_id: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    gap_type: Mapped[str] = mapped_column(String(48), default='')  # BUSINESS_RULE_MISSING 等 7 类
    severity: Mapped[str] = mapped_column(String(16), default='HIGH')  # CRITICAL/HIGH/MEDIUM/LOW
    description: Mapped[str] = mapped_column(Text, default='')
    question: Mapped[str] = mapped_column(Text, default='')  # 需产品确认项
    status: Mapped[str] = mapped_column(String(16), default='pending')  # pending/confirmed/ignored
    confirmed_by: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestPoint(Base):
    """测试点 — Story 确认后生成，回答「测什么」，以树形组织。"""
    __tablename__ = 'test_points'
    __table_args__ = (
        Index('idx_tp_requirement_id', 'requirement_id'),
        Index('idx_tp_story_id', 'story_id'),
        Index('idx_tp_parent_id', 'parent_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    story_id: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)  # 树形层级
    category: Mapped[str] = mapped_column(String(32), default='Functional')  # 11 类
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default='generated')  # generated/reviewed/confirmed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestPointReview(Base):
    """测试点评审 — 对某需求的测试点组整体评审（11 维 + QualityGate）。"""
    __tablename__ = 'test_point_reviews'
    __table_args__ = (
        Index('idx_tpr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    dimension_scores: Mapped[str] = mapped_column(Text, default='')  # JSON：11 维评分
    coverage: Mapped[str] = mapped_column(Text, default='')  # JSON：覆盖情况
    issues: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    suggestions: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestScenario(Base):
    """测试场景 — TestPoint 确认后生成，回答「在什么业务情况下测」。"""
    __tablename__ = 'test_scenarios'
    __table_args__ = (
        Index('idx_ts_requirement_id', 'requirement_id'),
        Index('idx_ts_test_point_id', 'test_point_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    test_point_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')  # 业务情况描述
    coverage_dim: Mapped[str] = mapped_column(String(32), default='')  # 覆盖维度（正常/异常/边界/状态）
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScenarioReview(Base):
    """场景评审 — 对某需求的场景集整体评审。"""
    __tablename__ = 'scenario_reviews'
    __table_args__ = (
        Index('idx_sr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[str] = mapped_column(Text, default='')  # JSON：场景覆盖情况
    issues: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    suggestions: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CaseReview(Base):
    """用例评审 — 对某需求的用例集整体评审（9 维检查 + QualityGate）。"""
    __tablename__ = 'case_reviews'
    __table_args__ = (
        Index('idx_cr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    checks: Mapped[str] = mapped_column(Text, default='')  # JSON：9 维检查结果
    issues: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    suggestions: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestStrategy(Base):
    """测试策略 — 需求级自动化/半自动化/人工推荐。"""
    __tablename__ = 'test_strategies'
    __table_args__ = (
        Index('idx_tstr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    automation_ratio: Mapped[int] = mapped_column(Integer, default=0)  # 建议自动化占比 0-100
    result: Mapped[str] = mapped_column(Text, default='')  # JSON：策略推荐明细
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReviewAudit(Base):
    """AI Review 审计 — 每次智能体评审落一条，保证测试设计过程可审计。"""
    __tablename__ = 'review_audits'
    __table_args__ = (
        Index('idx_rva_artifact', 'artifact_type', 'artifact_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)  # requirement/story/test_points/scenarios/cases
    artifact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    dimension_scores: Mapped[str] = mapped_column(Text, default='')  # JSON
    issues: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    suggestions: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    information_gaps: Mapped[str] = mapped_column(Text, default='')  # JSON 数组
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    model: Mapped[str] = mapped_column(String(128), default='')
    prompt_version: Mapped[str] = mapped_column(String(64), default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoverageSnapshot(Base):
    """覆盖率快照 — 按层计算（Requirement/Story/TestPoint/Scenario/Case/Automation/Risk）。"""
    __tablename__ = 'coverage_snapshots'
    __table_args__ = (
        Index('idx_cov_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_coverage: Mapped[int] = mapped_column(Integer, default=0)
    story_coverage: Mapped[int] = mapped_column(Integer, default=0)
    test_point_coverage: Mapped[int] = mapped_column(Integer, default=0)
    scenario_coverage: Mapped[int] = mapped_column(Integer, default=0)
    case_coverage: Mapped[int] = mapped_column(Integer, default=0)
    automation_coverage: Mapped[int] = mapped_column(Integer, default=0)
    risk_coverage: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[str] = mapped_column(Text, default='')  # JSON：各层明细
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestGap(Base):
    """测试缺口 — 覆盖率/风险推导出的缺口（P0/P1），驱动 AI 补测。"""
    __tablename__ = 'test_gaps'
    __table_args__ = (
        Index('idx_tg_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    layer: Mapped[str] = mapped_column(String(32), default='')  # story/test_point/scenario/case/automation/risk
    description: Mapped[str] = mapped_column(Text, default='')
    severity: Mapped[str] = mapped_column(String(4), default='P1')  # P0/P1
    status: Mapped[str] = mapped_column(String(16), default='open')  # open/closed
    source_ref: Mapped[str] = mapped_column(String(128), default='')  # 关联 story_id/test_point_id 等
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class AITask(Base):
    """AI 任务状态机 — 每个智能体环节一次调用的状态落库（PRD 第 8 节）。

    流转：PENDING → RUNNING → REVIEW → WAITING_HUMAN → CONFIRMED → NEXT_STAGE；
    异常：RUNNING → FAILED → RETRY。供前端轮询展示任务进度。
    """
    __tablename__ = 'ai_tasks'
    __table_args__ = (
        Index('idx_ait_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # analyze/review_stories/test_points/scenarios/cases/strategy/coverage
    status: Mapped[str] = mapped_column(String(16), default='PENDING')  # PENDING/RUNNING/REVIEW/WAITING_HUMAN/CONFIRMED/NEXT_STAGE/FAILED/RETRY
    error: Mapped[str] = mapped_column(Text, default='')
    model: Mapped[str] = mapped_column(String(128), default='')
    prompt_version: Mapped[str] = mapped_column(String(64), default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ══════════════════════════════════════════════════════════
# ADR-0016 新增模型 — 统一资产表
# ══════════════════════════════════════════════════════════


class RequirementAsset(Base):
    """统一分层资产表 — 替代 12 张独立分层表。

    asset_type 区分层级：analysis / story / story_review / test_point /
    test_point_review / scenario / scenario_review / case / case_review / strategy

    parent_id 支持树形层级（TestPoint 树、Scenario→TestPoint 引用）。
    story_id 支持 Story→Story 引用和 Case→Story 引用。
    content 存储各层可变结构化数据（JSON 格式）。
    """
    __tablename__ = 'requirement_assets'
    __table_args__ = (
        Index('idx_ra_requirement_id', 'requirement_id'),
        Index('idx_ra_asset_type', 'requirement_id', 'asset_type'),
        Index('idx_ra_parent_id', 'parent_id'),
        Index('idx_ra_story_id', 'story_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    story_id: Mapped[int] = mapped_column(Integer, default=0)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')

    # JSON content — 各层可变结构化数据（评分维度/步骤/覆盖率等）
    content: Mapped[str] = mapped_column(Text, default='')

    # 评审元数据（story_review / test_point_review / scenario_review / case_review）
    score: Mapped[int] = mapped_column(Integer, default=0)
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default='generated')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
