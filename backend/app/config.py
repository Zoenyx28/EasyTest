"""Centralized backend configuration loaded from the project-root .env file.

All infrastructure connection settings (database, Redis, Celery) are read here
so that they stay consistent across the API, WebSocket and Celery processes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Project root: .../data_annotation (standard layout) or /app (Docker layout)
_candidate = Path(__file__).resolve().parent.parent.parent
if (_candidate / 'backend' / 'app' / 'main.py').exists():
    PROJECT_ROOT = _candidate  # Standard: data_annotation/
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Docker: /app/

# Load .env from the project root (no-op if the file is absent).
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://insist_test:insist_test@10.19.83.140:39306/test_platform?charset=utf8mb4",
)

REDIS_URL = os.getenv("REDIS_URL", "redis://:zoenyx123@139.155.150.242:6379/0")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

# ── Project data storage paths ──
# Default is relative to project root, works in both dev (WSL) and Docker.
# Override via PROJECTS_DATA_DIR env var in Docker compose or production.
_DEFAULT_DATA_DIR = str(PROJECT_ROOT / "data" / "projects")
PROJECTS_DATA_DIR = Path(os.getenv("PROJECTS_DATA_DIR", _DEFAULT_DATA_DIR))

# 项目代码统一保存路径(cloned Git repos / copied local projects)
PROJECTS_SOURCE_DIR = PROJECTS_DATA_DIR / "source"

# 项目执行报告统一保存路径
PROJECTS_REPORT_DIR = PROJECTS_DATA_DIR / "reports"

# 项目级虚拟环境统一保存路径
PROJECTS_VENV_DIR = PROJECTS_DATA_DIR / "venvs"

# ── JWT authentication ──
JWT_SECRET = os.getenv("JWT_SECRET", "easy-test-jwt-secret-key-change-in-production")
