"""Requirement Design domain models — requirements, assets, AI tasks, coverage.

This domain owns the unified `RequirementAsset` table (ADR-0016) which
replaces the 12 legacy layered-test-design tables.  The legacy ORM models
are still present here (RequirementSource, RequirementReview, Story, etc.)
so existing CRUD code continues to function; they will be consolidated into
RequirementAsset over subsequent tickets.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


# ── Core requirement entity ──


class Requirement(Base):
    """Requirement record — scoped by (project_id, branch_id).

    State machine: pending_review → review_passed → story_confirmed → cases_generated → done
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

    # ADR-0016: source info embedded (replaces standalone requirement_sources table)
    content: Mapped[str] = mapped_column(Text, default='')
    source_type: Mapped[str] = mapped_column(String(16), default='text')
    source_meta: Mapped[str] = mapped_column(Text, default='')

    priority: Mapped[str] = mapped_column(String(16), default='P2')
    status: Mapped[str] = mapped_column(String(32), default='pending_review')
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── ADR-0016: Unified asset table ──


class RequirementAsset(Base):
    """Unified layered asset table — replaces 12 legacy layered tables.

    asset_type identifies the layer: analysis / story / story_review / test_point /
    test_point_review / scenario / scenario_review / case / case_review / strategy

    parent_id supports tree hierarchies (TestPoint tree, Scenario→TestPoint ref).
    story_id supports Story→Story and Case→Story references.
    content stores layer-specific variable structured data (JSON format).
    """
    __tablename__ = 'requirement_assets'
    __table_args__ = (
        Index('idx_rqas_requirement_id', 'requirement_id'),
        Index('idx_rqas_asset_type', 'requirement_id', 'asset_type'),
        Index('idx_rqas_parent_id', 'parent_id'),
        Index('idx_rqas_story_id', 'story_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    story_id: Mapped[int] = mapped_column(Integer, default=0)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')

    # JSON content — layer-specific structured data (score dimensions / steps / coverage etc.)
    content: Mapped[str] = mapped_column(Text, default='')

    # Review metadata (story_review / test_point_review / scenario_review / case_review)
    score: Mapped[int] = mapped_column(Integer, default=0)
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default='generated')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Case binding ──


class CaseBinding(Base):
    """Generated case ↔ automated test case (TestCaseDefinition) 0..N binding."""
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


# ── AI Task state machine ──


class AITask(Base):
    """AI task state machine — one record per agent invocation (PRD §8).

    States: PENDING → RUNNING → REVIEW → WAITING_HUMAN → CONFIRMED → NEXT_STAGE;
    error path: RUNNING → FAILED → RETRY.  Frontend polls for progress display.
    """
    __tablename__ = 'ai_tasks'
    __table_args__ = (
        Index('idx_ait_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='PENDING')
    error: Mapped[str] = mapped_column(Text, default='')
    model: Mapped[str] = mapped_column(String(128), default='')
    prompt_version: Mapped[str] = mapped_column(String(64), default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ══════════════════════════════════════════════════════════
# Legacy layered-test-design models (pre-ADR-0016)
# These remain for backward compatibility and will be
# progressively migrated to RequirementAsset.
# ══════════════════════════════════════════════════════════


class RequirementSource(Base):
    """Requirement source — lark link or offline file (txt/json/md/doc/docx/pdf/images)."""
    __tablename__ = 'requirement_sources'
    __table_args__ = (
        Index('idx_rs_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(16), default='lark_link')
    link: Mapped[str] = mapped_column(String(1024), default='')
    text_content: Mapped[str] = mapped_column(Text(length=2**24), default='')
    filename: Mapped[str] = mapped_column(String(256), default='')
    filepath: Mapped[str] = mapped_column(String(512), default='')
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(64), default='')
    extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    extract_error: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RequirementReview(Base):
    """Requirement review results — overwritten on each re-review, carries AI score."""
    __tablename__ = 'requirement_reviews'
    __table_args__ = (
        Index('idx_rr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, default='')
    risks: Mapped[str] = mapped_column(Text, default='')
    issues: Mapped[str] = mapped_column(Text, default='')
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_reason: Mapped[str] = mapped_column(Text, default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Story(Base):
    """Story decomposition result — belongs to a requirement, AI score stored inline."""
    __tablename__ = 'stories'
    __table_args__ = (
        Index('idx_story_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    acceptance_criteria: Mapped[str] = mapped_column(Text, default='')
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_reason: Mapped[str] = mapped_column(Text, default='')
    dimension_scores: Mapped[str] = mapped_column(Text, default='')
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    dependencies: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GeneratedCase(Base):
    """Agent-generated test case — can bind to automated test case."""
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
    steps: Mapped[str] = mapped_column(Text, default='')
    expected: Mapped[str] = mapped_column(Text, default='')
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_reason: Mapped[str] = mapped_column(Text, default='')
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RequirementAnalysis(Base):
    """Requirement analysis — AI understanding output, identifies business elements & gaps."""
    __tablename__ = 'requirement_analyses'
    __table_args__ = (
        Index('idx_ra_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    elements: Mapped[str] = mapped_column(Text, default='')
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_reason: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InformationGap(Base):
    """Information gap — created when requirement info is insufficient, needs PM confirmation."""
    __tablename__ = 'information_gaps'
    __table_args__ = (
        Index('idx_ig_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    story_id: Mapped[int] = mapped_column(Integer, default=0)
    project_id: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int] = mapped_column(Integer, default=0)
    gap_type: Mapped[str] = mapped_column(String(48), default='')
    severity: Mapped[str] = mapped_column(String(16), default='HIGH')
    description: Mapped[str] = mapped_column(Text, default='')
    question: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(16), default='pending')
    confirmed_by: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestPoint(Base):
    """Test point — generated after Story confirmed, answers "what to test", tree-organized."""
    __tablename__ = 'test_points'
    __table_args__ = (
        Index('idx_tp_requirement_id', 'requirement_id'),
        Index('idx_tp_story_id', 'story_id'),
        Index('idx_tp_parent_id', 'parent_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    story_id: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(32), default='Functional')
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default='generated')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestPointReview(Base):
    """Test point review — whole-group review for a requirement's test points (11-dim + QualityGate)."""
    __tablename__ = 'test_point_reviews'
    __table_args__ = (
        Index('idx_tpr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    dimension_scores: Mapped[str] = mapped_column(Text, default='')
    coverage: Mapped[str] = mapped_column(Text, default='')
    issues: Mapped[str] = mapped_column(Text, default='')
    suggestions: Mapped[str] = mapped_column(Text, default='')
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestScenario(Base):
    """Test scenario — generated after TestPoint confirmed, answers "under what business conditions"."""
    __tablename__ = 'test_scenarios'
    __table_args__ = (
        Index('idx_ts_requirement_id', 'requirement_id'),
        Index('idx_ts_test_point_id', 'test_point_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    test_point_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    coverage_dim: Mapped[str] = mapped_column(String(32), default='')
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScenarioReview(Base):
    """Scenario review — whole-group review for a requirement's scenario set."""
    __tablename__ = 'scenario_reviews'
    __table_args__ = (
        Index('idx_sr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[str] = mapped_column(Text, default='')
    issues: Mapped[str] = mapped_column(Text, default='')
    suggestions: Mapped[str] = mapped_column(Text, default='')
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CaseReview(Base):
    """Case review — whole-group review for a requirement's case set (9-dim check + QualityGate)."""
    __tablename__ = 'case_reviews'
    __table_args__ = (
        Index('idx_cr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    checks: Mapped[str] = mapped_column(Text, default='')
    issues: Mapped[str] = mapped_column(Text, default='')
    suggestions: Mapped[str] = mapped_column(Text, default='')
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    review_comment: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestStrategy(Base):
    """Test strategy — requirement-level automation/semi-auto/manual recommendation."""
    __tablename__ = 'test_strategies'
    __table_args__ = (
        Index('idx_tstr_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    automation_ratio: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReviewAudit(Base):
    """AI Review audit — one record per agent review, ensures test design process auditability."""
    __tablename__ = 'review_audits'
    __table_args__ = (
        Index('idx_rva_artifact', 'artifact_type', 'artifact_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    dimension_scores: Mapped[str] = mapped_column(Text, default='')
    issues: Mapped[str] = mapped_column(Text, default='')
    suggestions: Mapped[str] = mapped_column(Text, default='')
    information_gaps: Mapped[str] = mapped_column(Text, default='')
    gate_status: Mapped[str] = mapped_column(String(16), default='')
    model: Mapped[str] = mapped_column(String(128), default='')
    prompt_version: Mapped[str] = mapped_column(String(64), default='')
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoverageSnapshot(Base):
    """Coverage snapshot — per-layer calculation (Requirement/Story/TestPoint/Scenario/Case/Automation/Risk)."""
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
    details: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestGap(Base):
    """Test gap — coverage/risk derived gaps (P0/P1), drives AI supplementary testing."""
    __tablename__ = 'test_gaps'
    __table_args__ = (
        Index('idx_tg_requirement_id', 'requirement_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    layer: Mapped[str] = mapped_column(String(32), default='')
    description: Mapped[str] = mapped_column(Text, default='')
    severity: Mapped[str] = mapped_column(String(4), default='P1')
    status: Mapped[str] = mapped_column(String(16), default='open')
    source_ref: Mapped[str] = mapped_column(String(128), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
