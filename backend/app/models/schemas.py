"""Pydantic data models for the test management platform."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


# ── Branch ──

class BranchInfo(BaseModel):
    id: int
    project_id: int
    name: str
    source_branch_id: int | None = None
    is_default: bool = False
    is_empty: bool = False
    source_path: str = ''
    test_path: str = ''
    created_at: str = ''
    updated_at: str = ''


class BranchCreate(BaseModel):
    name: str
    source_branch_id: int | None = None


# ── Discovery ──

class TestCaseInfo(BaseModel):
    uid: str
    name: str
    methodName: str
    className: str
    module: str
    fullName: str
    description: str = ''
    steps: str | None = ''  # JSON string of test steps, e.g. [{"type":"api","description":"调用login接口","code":"auth_api.login"}]
    tags: list[str] = []
    filePath: str = ''
    testType: str = 'api'
    status: str = 'unknown'
    selected: bool = False  # for TreeView checkboxes
    isNew: bool = False


class TestClassInfo(BaseModel):
    name: str
    items: list[TestCaseInfo]
    total: int
    passed: int = 0
    failed: int = 0
    broken: int = 0
    expanded: bool = False


class TestModuleInfo(BaseModel):
    module: str
    classes: list[TestClassInfo]
    total: int
    passed: int = 0
    expanded: bool = False


class DiscoverResponse(BaseModel):
    modules: list[TestModuleInfo]
    total: int


# ── Execution ──

class RunRequest(BaseModel):
    uids: list[str] = []        # empty = all
    concurrency: int = 2
    env: str = 'test'
    smoke_only: bool = False
    sequential: bool = False    # True = run tests one by one


class TestHistoryItem(BaseModel):
    uid: str
    status: str
    duration_ms: int
    message: str | None = ''
    executed_at: str = ''
    run_id: str = ''


class RunLogDetail(BaseModel):
    uid: str
    status: str
    duration_ms: int
    message: str = ''
    trace: str = ''
    logs: str = ''
    executed_at: str = ''


# ── Report ──

class ReportSummary(BaseModel):
    total: int
    passed: int
    failed: int
    broken: int
    skipped: int
    xfailed: int
    passRate: float
    totalDuration: str
    totalDurationMs: int
    generatedAt: str
    host: str


class ReportItem(BaseModel):
    name: str
    uid: str
    methodName: str
    className: str
    module: str
    fullName: str
    status: str
    description: str
    duration: str
    duration_ms: int
    message: str
    trace: str
    logs: str
    tags: list[str]
    params: str
    history: list[dict[str, Any]] = []


class ReportClassInfo(BaseModel):
    name: str
    items: list[ReportItem]
    total: int
    passed: int
    failed: int
    broken: int


class ReportModuleInfo(BaseModel):
    module: str
    classes: list[ReportClassInfo]
    total: int
    passed: int


class ReportData(BaseModel):
    summary: ReportSummary
    moduleGroups: list[ReportModuleInfo]
    allTags: list[str] = []


# ── Project ──

class ProjectInfo(BaseModel):
    id: int
    name: str
    source_type: str
    server_path: str = ''
    test_path: str = ''
    report_output: str = ''
    source_path: str = ''          # 项目源码在服务器上的实际路径
    report_path: str = ''          # 执行报告在服务器上的存储路径
    is_active: bool = False
    case_count: int = 0
    new_case_count: int = 0
    creator_id: int = 0
    creator_name: str = ''
    member_count: int = 0
    last_synced_at: str = ''
    created_at: str = ''


class ProjectCreate(BaseModel):
    name: str
    source_type: str
    server_path: str = ''
    test_path: str = ''
    report_output: str = ''


class ProjectSyncResult(BaseModel):
    project_id: int
    case_count: int
    new_case_count: int
    added_count: int
    deleted_count: int


# ── Project Note ──

class ProjectNoteUpdate(BaseModel):
    content: str  # Markdown content


class ProjectNoteInfo(BaseModel):
    id: int
    project_id: int
    content: str
    updated_by: int
    updated_by_name: str = ''
    created_at: str
    updated_at: str


# ── User / Auth ──

class UserRegister(BaseModel):
    username: str
    nickname: str
    password: str
    avatar: str = ''  # 'default:1'~'default:5' or custom path


class UserLogin(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: int
    username: str
    nickname: str
    avatar_url: str = ''
    created_at: str = ''


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class UserSearchResult(BaseModel):
    id: int
    username: str
    nickname: str
    avatar_url: str = ''


# ── Project Member ──

class ProjectMemberAdd(BaseModel):
    user_id: int


class ProjectMemberInfo(BaseModel):
    id: int
    user_id: int
    username: str = ''
    nickname: str = ''
    avatar_url: str = ''
    created_at: str = ''


# ── Defect Management ──


class DefectModuleCreate(BaseModel):
    name: str
    parent_id: int = 0
    sort_order: int = 0


class DefectModuleInfo(BaseModel):
    id: int
    project_id: int
    name: str
    parent_id: int
    sort_order: int
    children: list = []


class DefectCreate(BaseModel):
    title: str
    description: str = ''
    steps: str = ''
    project_id: int
    branch_id: int
    module_id: int = 0
    severity: str = 'P3'
    priority: str = 'P3'
    assignee_id: int = 0
    case_uid: str = ''
    bug_type: str = 'code_error'
    deadline: str = ''
    attachments: list[dict] = []


class DefectUpdate(BaseModel):
    title: str = ''
    description: str = ''
    steps: str = ''
    module_id: Optional[int] = None
    severity: str = ''
    priority: str = ''
    assignee_id: Optional[int] = None
    case_uid: Optional[str] = None
    bug_type: str = ''
    deadline: str = ''
    resolved_version: int = 0
    resolved_date: str = ''
    attachments: list[dict] = []


class DefectTransition(BaseModel):
    action: str  # confirm/assign/resolve/close/activate
    assignee_id: int = 0
    resolution: str = ''
    comment: str = ''
    resolved_version: int = 0
    duplicate_defect_id: int = 0
    bug_type: str = ''
    priority: str = ''
    deadline: str = ''


class DefectInfo(BaseModel):
    id: int
    title: str
    description: str
    steps: str
    project_id: int
    branch_id: int
    module_id: int
    module_name: str = ''
    severity: str
    priority: str
    status: str
    resolution: str = ''
    assignee_id: int = 0
    assignee_name: str = ''
    creator_id: int
    creator_name: str = ''
    bug_type: str = ''
    bug_type_name: str = ''
    deadline: str = ''
    resolved_version: int = 0
    resolved_version_name: str = ''
    duplicate_defect_id: int = 0
    duplicate_defect_title: str = ''
    resolved_date: str = ''
    created_at: str
    updated_at: str


class DefectLogInfo(BaseModel):
    id: int
    field: str
    old_value: str = ''
    new_value: str = ''
    operator_id: int
    operator_name: str = ''
    created_at: str


class DefectAttachmentInfo(BaseModel):
    id: int
    filename: str
    file_size: int
    mime_type: str
    created_by: int
    created_at: str


class DefectCommentCreate(BaseModel):
    content: str


class DefectCommentInfo(BaseModel):
    id: int
    defect_id: int
    content: str
    author_id: int
    author_name: str = ''
    created_at: str
    updated_at: str
