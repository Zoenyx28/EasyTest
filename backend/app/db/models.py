"""Backward-compatibility re-exports of all ORM models.

ALL models have been moved to domain-specific and shared modules:
  - app.shared.models          — User, LLMSettings, UserLarkBinding
  - app.domains.project_mgmt   — Project, Branch, ProjectMember, ProjectNote,
                                  UserActiveProject, ProjectCase
  - app.domains.test_execution  — TestCaseDefinition, Task, TaskCase, Execution,
                                  ExecutionCase, Report
  - app.domains.defect_tracking — DefectModule, Defect, DefectAttachment,
                                  DefectLog, DefectComment
  - app.domains.requirement_design — Requirement, RequirementAsset, RequirementSource,
                                  RequirementReview, Story, GeneratedCase, CaseBinding,
                                  RequirementAnalysis, InformationGap, TestPoint,
                                  TestPointReview, TestScenario, ScenarioReview,
                                  CaseReview, TestStrategy, ReviewAudit,
                                  CoverageSnapshot, TestGap, AITask

This file is retained for backward compatibility only.
Prefer importing from the canonical domain locations in new code.
"""
# Shared models
from app.shared.models import User, LLMSettings, UserLarkBinding  # noqa: F401, E402

# Project management domain
from app.domains.project_mgmt.models import (  # noqa: F401, E402
    Branch, Project, ProjectCase, ProjectMember, ProjectNote, UserActiveProject,
)

# Test execution domain
from app.domains.test_execution.models import (  # noqa: F401, E402
    TestCaseDefinition, Task, TaskCase, Execution, ExecutionCase, Report,
)

# Defect tracking domain
from app.domains.defect_tracking.models import (  # noqa: F401, E402
    DefectModule, Defect, DefectAttachment, DefectLog, DefectComment,
)

# Requirement design domain
from app.domains.requirement_design.models import (  # noqa: F401, E402
    Requirement, RequirementAsset, RequirementSource, RequirementReview,
    Story, GeneratedCase, CaseBinding,
    RequirementAnalysis, InformationGap, TestPoint, TestPointReview,
    TestScenario, ScenarioReview, CaseReview, TestStrategy,
    ReviewAudit, CoverageSnapshot, TestGap, AITask,
)
