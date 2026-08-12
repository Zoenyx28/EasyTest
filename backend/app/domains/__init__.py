"""Domain models module — backward-compat re-exports.

All models have been moved to per-domain model files.
This package remains importable but new code should import from the
canonical domain locations directly.
"""
# This package exists for import-path compatibility.
# Domain modules are imported directly, e.g.:
#   from app.domains.requirement_design.models import Requirement
#   from app.domains.defect_tracking.models import Defect
#   from app.domains.test_execution.models import Execution
#   from app.domains.project_mgmt.models import Project
