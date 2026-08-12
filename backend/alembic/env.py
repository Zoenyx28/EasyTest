"""Alembic environment configuration for async SQLAlchemy."""
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure backend package is on path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import DATABASE_URL
from app.shared.database import Base

# Import all domain models so Base.metadata is populated
from app.shared.models import User, LLMSettings, UserLarkBinding  # noqa: F401
from app.domains.project_mgmt.models import Project, Branch, ProjectMember, ProjectNote, UserActiveProject  # noqa: F401
from app.domains.test_execution.models import TestCaseDefinition, Task, TaskCase, Execution, ExecutionCase, Report  # noqa: F401
from app.domains.defect_tracking.models import DefectModule, Defect, DefectAttachment, DefectLog, DefectComment  # noqa: F401
from app.domains.requirement_design.models import Requirement, RequirementAsset, CaseBinding, AITask, ReviewAudit, CoverageSnapshot, TestGap  # noqa: F401

# Alembic Config object
config = context.config

# Override sqlalchemy.url from our config
config.set_main_option('sqlalchemy.url', DATABASE_URL)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Execute migrations with the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
