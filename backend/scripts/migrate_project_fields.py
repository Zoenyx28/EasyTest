"""Database migration: add server_path column and migrate project fields.

Run this script after deploying the new backend code.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import session_ctx
from app.db.models import Project
from sqlalchemy import select, text


async def migrate():
    print("=" * 60)
    print("Step 1: Adding server_path column if not exists")
    print("=" * 60)

    async with session_ctx() as session:
        try:
            await session.execute(text("""
                ALTER TABLE projects
                ADD COLUMN IF NOT EXISTS server_path VARCHAR(1024) NOT NULL DEFAULT ''
            """))
            await session.commit()
            print("server_path column added/verified.")
        except Exception as e:
            await session.rollback()
            print(f"Warning: Could not add server_path column: {e}")
            print("Trying MySQL-compatible syntax...")
            # MySQL doesn't support IF NOT EXISTS for columns
            async with session_ctx() as session:
                try:
                    # Check if column exists first
                    result = await session.execute(text("""
                        SELECT COUNT(*) as cnt FROM information_schema.COLUMNS
                        WHERE TABLE_NAME = 'projects' AND COLUMN_NAME = 'server_path'
                    """))
                    row = result.fetchone()
                    if row and row[0] == 0:
                        await session.execute(text("""
                            ALTER TABLE projects
                            ADD COLUMN server_path VARCHAR(1024) NOT NULL DEFAULT ''
                        """))
                        await session.commit()
                        print("server_path column added (MySQL syntax).")
                    else:
                        print("server_path column already exists.")
                except Exception as e2:
                    print(f"Warning: {e2}")
                    print("Please add the column manually: ALTER TABLE projects ADD COLUMN server_path VARCHAR(1024) NOT NULL DEFAULT '';")

    print("\n" + "=" * 60)
    print("Step 2: Migrating existing project data")
    print("=" * 60)

    async with session_ctx() as session:
        result = await session.execute(select(Project))
        projects = result.scalars().all()

        if not projects:
            print("No projects found to migrate.")
            return

        for p in projects:
            old_type = p.source_type

            if old_type == 'git':
                new_server_path = getattr(p, 'git_url', '') or getattr(p, 'local_path', '') or ''
                print(f"  [{p.id}] {p.name}: git → server (path: {new_server_path})")
                p.source_type = 'server'
                p.server_path = new_server_path
            elif old_type == 'local':
                new_server_path = getattr(p, 'local_path', '') or ''
                print(f"  [{p.id}] {p.name}: local → server (path: {new_server_path})")
                p.source_type = 'server'
                p.server_path = new_server_path
            else:
                print(f"  [{p.id}] {p.name}: {old_type} → (unchanged)")

        await session.commit()

    print("\n" + "=" * 60)
    print("Step 3: Dropping old columns")
    print("=" * 60)

    async with session_ctx() as session:
        try:
            # MySQL syntax for dropping columns
            for col in ['git_url', 'git_branch', 'git_auth', 'git_subdir', 'local_path']:
                try:
                    await session.execute(text(f"ALTER TABLE projects DROP COLUMN IF EXISTS {col}"))
                except Exception:
                    try:
                        await session.execute(text(f"ALTER TABLE projects DROP COLUMN {col}"))
                    except Exception:
                        print(f"  Skipping drop of {col} (may not exist)")
            await session.commit()
            print("Old columns dropped successfully.")
        except Exception as e:
            await session.rollback()
            print(f"Warning: Could not drop old columns: {e}")
            print("You may need to drop them manually.")

    print("\n" + "=" * 60)
    print("✓ Migration complete!")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(migrate())