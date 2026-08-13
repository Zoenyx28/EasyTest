"""Database engine and session management (backward-compat re-exports).

Base, engine, async_session_factory, and session_ctx are now defined in
app.shared.database.  This file re-exports them and retains init_db()
which will be progressively migrated to Alembic over subsequent tickets.
"""
from sqlalchemy import text

# Re-export from the canonical location
from app.shared.database import Base, engine, async_session_factory, session_ctx, get_session  # noqa: F401, E402


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
        "ALTER TABLE requirement_sources ADD COLUMN extract_error TEXT",
        "ALTER TABLE requirement_reviews ADD COLUMN gate_status VARCHAR(16) DEFAULT ''",
        "ALTER TABLE stories ADD COLUMN gate_status VARCHAR(16) DEFAULT ''",
        "ALTER TABLE generated_cases ADD COLUMN gate_status VARCHAR(16) DEFAULT ''",
        # ADR-0016: Requirement source embedding + Defect traceability
        "ALTER TABLE requirements ADD COLUMN content TEXT DEFAULT ''",
        "ALTER TABLE requirements ADD COLUMN source_type VARCHAR(16) DEFAULT 'text'",
        "ALTER TABLE requirements ADD COLUMN source_meta TEXT DEFAULT ''",
        "ALTER TABLE defects ADD COLUMN requirement_id INTEGER DEFAULT 0",
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

    # ── stories 新列（PRD V2.0）──
    # MySQL 5.7 的 TEXT 列不允许 DEFAULT 值，需先查 information_schema 判断列是否
    # 已存在，存在则跳过（幂等），否则 ALTER 失败会被上面的 pass 静默吞掉导致缺列。
    try:
        async with engine.begin() as conn:
            for col, ddl in [
                ('dimension_scores', 'dimension_scores TEXT'),
                ('dependencies', 'dependencies TEXT'),
            ]:
                # aiomysql 的 exec_driver_sql 不支持命名参数，改用 conn.execute(text(...))
                res = await conn.execute(
                    text("SELECT COUNT(*) FROM information_schema.columns "
                         "WHERE table_schema = DATABASE() AND table_name = 'stories' "
                         "AND column_name = :c"),
                    {'c': col})
                if res.scalar() == 0:
                    await conn.exec_driver_sql(f'ALTER TABLE stories ADD COLUMN {ddl}')
    except Exception:
        pass

    # ── 长文档正文升级：TEXT(64KB) → MEDIUMTEXT(16MB)（MySQL 专属语法，幂等）──
    # 飞书文档正文（如产品需求设计文档）常超过 64KB，超限 INSERT 会失败（DataError 1366/1406）。
    if dialect == 'mysql':
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql(
                    "ALTER TABLE requirement_sources MODIFY text_content "
                    "MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
        except Exception as exc:
            print(f'[init_db] 升级 text_content 为 MEDIUMTEXT 失败: {exc}', flush=True)

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

    # ── Requirement Management tables ──
    dialect = engine.dialect.name
    autoinc = 'AUTO_INCREMENT' if dialect == 'mysql' else 'AUTOINCREMENT'
    on_update = ', updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP' if dialect == 'mysql' else ''
    # 飞书文档正文可能超过 TEXT(64KB) 上限，MySQL 用 MEDIUMTEXT(16MB)，SQLite 忽略长度用 TEXT
    mediumtext = 'MEDIUMTEXT' if dialect == 'mysql' else 'TEXT'
    requirement_tables = [
        "CREATE TABLE IF NOT EXISTS requirements ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "project_id INTEGER NOT NULL, "
        "branch_id INTEGER NOT NULL, "
        "title VARCHAR(512) NOT NULL, "
        "summary TEXT DEFAULT '', "
        "priority VARCHAR(16) DEFAULT 'P2', "
        "status VARCHAR(32) DEFAULT 'pending_review', "
        "created_by INTEGER NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP" + on_update +
        ")",
        "CREATE TABLE IF NOT EXISTS requirement_sources ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "type VARCHAR(16) DEFAULT 'lark_link', "
        "link VARCHAR(1024) DEFAULT '', "
        "text_content " + mediumtext + (" DEFAULT ''" if dialect == 'sqlite' else '') + ", "
        "filename VARCHAR(256) DEFAULT '', "
        "filepath VARCHAR(512) DEFAULT '', "
        "file_size INTEGER DEFAULT 0, "
        "mime_type VARCHAR(64) DEFAULT '', "
        "extracted BOOLEAN DEFAULT 0, "
        "extract_error TEXT DEFAULT '', "
        "created_by INTEGER NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS requirement_reviews ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "conclusion TEXT DEFAULT '', "
        "risks TEXT DEFAULT '', "
        "issues TEXT DEFAULT '', "
        "score INTEGER DEFAULT 0, "
        "score_reason TEXT DEFAULT '', "
        "review_comment TEXT DEFAULT '', "
        "created_by INTEGER NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS stories ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "title VARCHAR(512) NOT NULL, "
        "description TEXT DEFAULT '', "
        "acceptance_criteria TEXT DEFAULT '', "
        "sort_order INTEGER DEFAULT 0, "
        "score INTEGER DEFAULT 0, "
        "score_reason TEXT DEFAULT '', "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS generated_cases ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "story_id INTEGER DEFAULT 0, "
        "title VARCHAR(512) NOT NULL, "
        "preconditions TEXT DEFAULT '', "
        "steps TEXT DEFAULT '', "
        "expected TEXT DEFAULT '', "
        "score INTEGER DEFAULT 0, "
        "score_reason TEXT DEFAULT '', "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS case_bindings ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "generated_case_id INTEGER NOT NULL, "
        "uid VARCHAR(64) NOT NULL, "
        "project_id INTEGER NOT NULL, "
        "branch_id INTEGER NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS llm_settings ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "provider VARCHAR(32) DEFAULT 'deepseek', "
        "api_base VARCHAR(512) DEFAULT '', "
        "text_model VARCHAR(128) DEFAULT '', "
        "vision_model VARCHAR(128) DEFAULT '', "
        "api_key VARCHAR(512) DEFAULT '', "
        "updated_by INTEGER DEFAULT 0, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP" + on_update +
        ")",
        "CREATE TABLE IF NOT EXISTS user_lark_bindings ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "user_id INTEGER NOT NULL, "
        "app_id VARCHAR(64) DEFAULT '', "
        "lark_open_id VARCHAR(128) DEFAULT '', "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP" + on_update +
        ")",
        # ── 飞书官方 API OAuth token（读阶段，替换 lark-cli keychain）──
        "CREATE TABLE IF NOT EXISTS user_feishu_tokens ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "user_id INTEGER NOT NULL, "
        "lark_open_id VARCHAR(128) DEFAULT '', "
        "access_token_enc TEXT DEFAULT '', "
        "refresh_token_enc TEXT DEFAULT '', "
        "access_expires_at DATETIME, "
        "refresh_expires_at DATETIME, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP" + on_update +
        ")",
        # ── PRD V2.0 分层测试设计表（#20）──
        "CREATE TABLE IF NOT EXISTS requirement_analyses ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "project_id INTEGER DEFAULT 0, "
        "branch_id INTEGER DEFAULT 0, "
        "elements TEXT DEFAULT '', "
        "score INTEGER DEFAULT 0, "
        "score_reason TEXT DEFAULT '', "
        "created_by INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS information_gaps ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "story_id INTEGER DEFAULT 0, "
        "project_id INTEGER DEFAULT 0, "
        "branch_id INTEGER DEFAULT 0, "
        "gap_type VARCHAR(48) DEFAULT '', "
        "severity VARCHAR(16) DEFAULT 'HIGH', "
        "description TEXT DEFAULT '', "
        "question TEXT DEFAULT '', "
        "status VARCHAR(16) DEFAULT 'pending', "
        "confirmed_by INTEGER DEFAULT 0, "
        "confirmed_at DATETIME, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS test_points ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "story_id INTEGER DEFAULT 0, "
        "parent_id INTEGER DEFAULT 0, "
        "category VARCHAR(32) DEFAULT 'Functional', "
        "title VARCHAR(512) NOT NULL, "
        "description TEXT DEFAULT '', "
        "sort_order INTEGER DEFAULT 0, "
        "status VARCHAR(16) DEFAULT 'generated', "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS test_point_reviews ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "score INTEGER DEFAULT 0, "
        "dimension_scores TEXT DEFAULT '', "
        "coverage TEXT DEFAULT '', "
        "issues TEXT DEFAULT '', "
        "suggestions TEXT DEFAULT '', "
        "gate_status VARCHAR(16) DEFAULT '', "
        "review_comment TEXT DEFAULT '', "
        "created_by INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS test_scenarios ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "test_point_id INTEGER NOT NULL, "
        "title VARCHAR(512) NOT NULL, "
        "description TEXT DEFAULT '', "
        "coverage_dim VARCHAR(32) DEFAULT '', "
        "sort_order INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS scenario_reviews ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "score INTEGER DEFAULT 0, "
        "coverage TEXT DEFAULT '', "
        "issues TEXT DEFAULT '', "
        "suggestions TEXT DEFAULT '', "
        "gate_status VARCHAR(16) DEFAULT '', "
        "review_comment TEXT DEFAULT '', "
        "created_by INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS case_reviews ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "score INTEGER DEFAULT 0, "
        "checks TEXT DEFAULT '', "
        "issues TEXT DEFAULT '', "
        "suggestions TEXT DEFAULT '', "
        "gate_status VARCHAR(16) DEFAULT '', "
        "review_comment TEXT DEFAULT '', "
        "created_by INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS test_strategies ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "automation_ratio INTEGER DEFAULT 0, "
        "result TEXT DEFAULT '', "
        "created_by INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS review_audits ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "artifact_type VARCHAR(32) NOT NULL, "
        "artifact_id INTEGER NOT NULL, "
        "score INTEGER DEFAULT 0, "
        "dimension_scores TEXT DEFAULT '', "
        "issues TEXT DEFAULT '', "
        "suggestions TEXT DEFAULT '', "
        "information_gaps TEXT DEFAULT '', "
        "gate_status VARCHAR(16) DEFAULT '', "
        "model VARCHAR(128) DEFAULT '', "
        "prompt_version VARCHAR(64) DEFAULT '', "
        "created_by INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS coverage_snapshots ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "requirement_coverage INTEGER DEFAULT 0, "
        "story_coverage INTEGER DEFAULT 0, "
        "test_point_coverage INTEGER DEFAULT 0, "
        "scenario_coverage INTEGER DEFAULT 0, "
        "case_coverage INTEGER DEFAULT 0, "
        "automation_coverage INTEGER DEFAULT 0, "
        "risk_coverage INTEGER DEFAULT 0, "
        "details TEXT DEFAULT '', "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS test_gaps ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "layer VARCHAR(32) DEFAULT '', "
        "description TEXT DEFAULT '', "
        "severity VARCHAR(4) DEFAULT 'P1', "
        "status VARCHAR(16) DEFAULT 'open', "
        "source_ref VARCHAR(128) DEFAULT '', "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "closed_at DATETIME"
        ")",
        # ── AI 任务状态机（#21）──
        "CREATE TABLE IF NOT EXISTS ai_tasks ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "stage VARCHAR(32) NOT NULL, "
        "status VARCHAR(16) DEFAULT 'PENDING', "
        "error TEXT DEFAULT '', "
        "model VARCHAR(128) DEFAULT '', "
        "prompt_version VARCHAR(64) DEFAULT '', "
        "created_by INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP" + on_update +
        ")",
    ]
    for sql in requirement_tables:
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql(sql)
        except Exception:
            pass

    # ── ADR-0016: 统一资产表 + 需求/缺陷新字段 ──
    adr0016_tables = []
    if dialect == 'mysql':
        autoinc = 'AUTO_INCREMENT'
    else:
        autoinc = 'AUTOINCREMENT'
    adr0016_tables.append(
        "CREATE TABLE IF NOT EXISTS requirement_assets ("
        "id INTEGER PRIMARY KEY " + autoinc + ", "
        "requirement_id INTEGER NOT NULL, "
        "asset_type VARCHAR(32) NOT NULL, "
        "parent_id INTEGER DEFAULT 0, "
        "story_id INTEGER DEFAULT 0, "
        "title VARCHAR(512) NOT NULL, "
        "description TEXT DEFAULT '', "
        "content TEXT DEFAULT '', "
        "score INTEGER DEFAULT 0, "
        "gate_status VARCHAR(16) DEFAULT '', "
        "review_comment TEXT DEFAULT '', "
        "sort_order INTEGER DEFAULT 0, "
        "status VARCHAR(16) DEFAULT 'generated', "
        "created_by INTEGER DEFAULT 0, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    for sql in adr0016_tables:
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
