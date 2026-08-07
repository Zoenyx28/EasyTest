"""Database engine and session management.

MySQL is the production default.  SQLite remains an explicit local fallback
(`DATABASE_URL=sqlite+aiosqlite:///...`) so contributors can inspect the API
without starting the middleware stack.
"""
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables on startup, then apply lightweight column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Lightweight migrations: create_all does not add columns to existing tables,
    # so we ALTER TABLE ADD COLUMN for the newly introduced columns.  Each ALTER
    # runs in its own transaction with try/except so that an already-existing
    # column (which raises an error) does not affect the other statements.
    # SQLite and MySQL share the same "ALTER TABLE t ADD COLUMN c type default"
    # syntax; both require adding one column at a time.
    migrations = [
        "ALTER TABLE test_case_definitions ADD COLUMN test_type VARCHAR(16) DEFAULT 'api'",
        "ALTER TABLE test_case_definitions ADD COLUMN file_path VARCHAR(512) DEFAULT ''",
        "ALTER TABLE test_case_definitions ADD COLUMN branch_id INTEGER DEFAULT 0",
        "ALTER TABLE test_case_definitions ADD COLUMN steps TEXT",
        "ALTER TABLE execution_cases ADD COLUMN test_type VARCHAR(16) DEFAULT 'api'",
        "ALTER TABLE execution_cases ADD COLUMN steps TEXT",
        "ALTER TABLE execution_cases ADD COLUMN screenshots TEXT",
        "ALTER TABLE execution_cases ADD COLUMN branch_id INTEGER DEFAULT 0",
        "ALTER TABLE execution_cases ADD COLUMN description TEXT",
        "ALTER TABLE test_results ADD COLUMN test_type VARCHAR(16) DEFAULT 'api'",
        "ALTER TABLE test_results ADD COLUMN steps TEXT",
        "ALTER TABLE test_results ADD COLUMN screenshots TEXT",
        "ALTER TABLE tasks ADD COLUMN branch_id INTEGER DEFAULT 0",
        "ALTER TABLE task_cases ADD COLUMN branch_id INTEGER DEFAULT 0",
        "ALTER TABLE executions ADD COLUMN branch_id INTEGER DEFAULT 0",
        "ALTER TABLE reports ADD COLUMN branch_id INTEGER DEFAULT 0",
        "ALTER TABLE projects ADD COLUMN creator_id INTEGER DEFAULT 0",
        "ALTER TABLE project_notes ADD COLUMN updated_at DATETIME",
        "ALTER TABLE project_notes ADD COLUMN updated_by INTEGER DEFAULT 0",
        "ALTER TABLE defect_modules ADD COLUMN branch_id INTEGER DEFAULT 0",
        "ALTER TABLE defects ADD COLUMN case_uid VARCHAR(256) DEFAULT ''",
        "ALTER TABLE defects ADD COLUMN case_name VARCHAR(512) DEFAULT ''",
        "CREATE TABLE IF NOT EXISTS project_members (id INTEGER PRIMARY KEY AUTO_INCREMENT, project_id INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)",
    ]

    dialect = engine.dialect.name  # 'sqlite' or 'mysql'
    _ = dialect  # syntax is identical for the columns above on both dialects

    for sql in migrations:
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql(sql)
        except Exception:
            pass

    # ── Composite primary key migration ──
    # Change test_case_definitions PK from (uid) to (uid, project_id, branch_id)
    # so that the same test UID can coexist across different projects/branches.
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                "ALTER TABLE test_case_definitions DROP PRIMARY KEY, "
                "ADD PRIMARY KEY (uid, project_id, branch_id)"
            )
    except Exception:
        pass

    # ── Defect Management tables ──
    dialect = engine.dialect.name
    if dialect == 'mysql':
        # MySQL-compatible tables
        defect_tables = [
            "CREATE TABLE IF NOT EXISTS defect_modules ("
            "id INTEGER PRIMARY KEY AUTO_INCREMENT, "
            "project_id INTEGER NOT NULL, "
            "name VARCHAR(64) NOT NULL, "
            "parent_id INTEGER DEFAULT 0, "
            "sort_order INTEGER DEFAULT 0, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")",
            "CREATE TABLE IF NOT EXISTS defects ("
            "id INTEGER PRIMARY KEY AUTO_INCREMENT, "
            "title VARCHAR(512) NOT NULL, "
            "description TEXT DEFAULT '', "
            "steps TEXT DEFAULT '', "
            "project_id INTEGER NOT NULL, "
            "branch_id INTEGER NOT NULL, "
            "module_id INTEGER DEFAULT 0, "
            "severity VARCHAR(16) DEFAULT 'P3', "
            "priority VARCHAR(16) DEFAULT 'P3', "
            "status VARCHAR(32) DEFAULT 'unconfirmed', "
            "resolution VARCHAR(64) DEFAULT '', "
            "assignee_id INTEGER DEFAULT 0, "
            "creator_id INTEGER NOT NULL, "
            "bug_type VARCHAR(32) DEFAULT 'code_error', "
            "deadline VARCHAR(32) DEFAULT '', "
            "resolved_version INTEGER DEFAULT 0, "
            "resolved_date VARCHAR(32) DEFAULT '', "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")",
            "CREATE TABLE IF NOT EXISTS defect_attachments ("
            "id INTEGER PRIMARY KEY AUTO_INCREMENT, "
            "defect_id INTEGER NOT NULL, "
            "filename VARCHAR(256) NOT NULL, "
            "filepath VARCHAR(512) NOT NULL, "
            "file_size INTEGER DEFAULT 0, "
            "mime_type VARCHAR(64) DEFAULT '', "
            "created_by INTEGER NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")",
            "CREATE TABLE IF NOT EXISTS defect_logs ("
            "id INTEGER PRIMARY KEY AUTO_INCREMENT, "
            "defect_id INTEGER NOT NULL, "
            "field VARCHAR(32) NOT NULL, "
            "old_value TEXT DEFAULT '', "
            "new_value TEXT DEFAULT '', "
            "operator_id INTEGER NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")",
            "CREATE TABLE IF NOT EXISTS defect_comments ("
            "id INTEGER PRIMARY KEY AUTO_INCREMENT, "
            "defect_id INTEGER NOT NULL, "
            "content TEXT NOT NULL, "
            "author_id INTEGER NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")",
        ]
    else:
        # SQLite-compatible tables
        defect_tables = [
            "CREATE TABLE IF NOT EXISTS defect_modules ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "project_id INTEGER NOT NULL, "
            "name VARCHAR(64) NOT NULL, "
            "parent_id INTEGER DEFAULT 0, "
            "sort_order INTEGER DEFAULT 0, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")",
            "CREATE TABLE IF NOT EXISTS defects ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title VARCHAR(512) NOT NULL, "
            "description TEXT DEFAULT '', "
            "steps TEXT DEFAULT '', "
            "project_id INTEGER NOT NULL, "
            "branch_id INTEGER NOT NULL, "
            "module_id INTEGER DEFAULT 0, "
            "severity VARCHAR(16) DEFAULT 'P3', "
            "priority VARCHAR(16) DEFAULT 'P3', "
            "status VARCHAR(32) DEFAULT 'unconfirmed', "
            "resolution VARCHAR(64) DEFAULT '', "
            "assignee_id INTEGER DEFAULT 0, "
            "creator_id INTEGER NOT NULL, "
            "bug_type VARCHAR(32) DEFAULT 'code_error', "
            "deadline VARCHAR(32) DEFAULT '', "
            "resolved_version INTEGER DEFAULT 0, "
            "resolved_date VARCHAR(32) DEFAULT '', "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")",
            "CREATE TABLE IF NOT EXISTS defect_attachments ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "defect_id INTEGER NOT NULL, "
            "filename VARCHAR(256) NOT NULL, "
            "filepath VARCHAR(512) NOT NULL, "
            "file_size INTEGER DEFAULT 0, "
            "mime_type VARCHAR(64) DEFAULT '', "
            "created_by INTEGER NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")",
            "CREATE TABLE IF NOT EXISTS defect_logs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "defect_id INTEGER NOT NULL, "
            "field VARCHAR(32) NOT NULL, "
            "old_value TEXT DEFAULT '', "
            "new_value TEXT DEFAULT '', "
            "operator_id INTEGER NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")",
            "CREATE TABLE IF NOT EXISTS defect_comments ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "defect_id INTEGER NOT NULL, "
            "content TEXT NOT NULL, "
            "author_id INTEGER NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")",
        ]
    for sql in defect_tables:
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql(sql)
        except Exception:
            pass

    # Drop legacy tables no longer managed by ORM
    drop_legacy = [
        "DROP TABLE IF EXISTS runs",
        "DROP TABLE IF EXISTS test_results",
    ]
    for sql in drop_legacy:
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql(sql)
        except Exception:
            pass


async def get_session() -> AsyncSession:
    """Yield an async session for dependency injection."""
    async with async_session_factory() as session:
        yield session


@asynccontextmanager
async def session_ctx():
    """Context manager for direct session use in services."""
    async with async_session_factory() as session:
        yield session
