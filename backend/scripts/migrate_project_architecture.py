"""
One-time migration script for project-level architecture refactor.

Steps:
1. Create a legacy project for existing TestCaseDefinition records without project_id.
2. Assign project_id to all existing TestCaseDefinition records.
3. Migrate reports/history.json to the reports database table.
4. Add project_id to existing Task and Execution records.
5. Verify migration results.

Run: python -m scripts.migrate_project_architecture
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import session_ctx
from app.db.models import TestCaseDefinition, Task, Execution, Project, Report
from sqlalchemy import select, delete


async def migrate():
    print("=" * 60)
    print("Project Architecture Migration")
    print("=" * 60)
    
    # Step 1: Create legacy project
    print("\n[Step 1/5] Creating legacy project...")
    legacy_project_id = None
    async with session_ctx() as session:
        result = await session.execute(select(Project).where(Project.name == 'Legacy'))
        legacy = result.scalar_one_or_none()
        if legacy:
            legacy_project_id = legacy.id
            print(f"  Legacy project already exists: id={legacy_project_id}")
        else:
            project = Project(name='Legacy', source_type='server', server_path='automation/')
            session.add(project)
            await session.flush()
            legacy_project_id = project.id
            await session.commit()
            print(f"  Created legacy project: id={legacy_project_id}")
    
    # Step 2: Assign project_id to TestCaseDefinition
    print("\n[Step 2/5] Assigning project_id to TestCaseDefinition records...")
    async with session_ctx() as session:
        result = await session.execute(
            select(TestCaseDefinition).where(TestCaseDefinition.project_id == 0)
        )
        unassigned = result.scalars().all()
        count = len(unassigned)
        for record in unassigned:
            record.project_id = legacy_project_id
        if count > 0:
            await session.commit()
        print(f"  Updated {count} TestCaseDefinition records -> project_id={legacy_project_id}")
    
    # Step 3: Migrate reports/history.json to database
    print("\n[Step 3/5] Migrating reports/history.json to database...")
    history_path = Path(__file__).resolve().parent.parent.parent / 'reports' / 'history.json'
    migrated_count = 0
    if history_path.exists():
        with open(history_path, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        if isinstance(history_data, list):
            for entry in history_data:
                execution_id = entry.get('execution_id', '')
                summary = entry.get('summary', {})
                results = entry.get('results', [])
                
                # Try to determine project_id from execution
                project_id = legacy_project_id
                if execution_id:
                    async with session_ctx() as session:
                        exec_result = await session.execute(
                            select(Execution).where(Execution.execution_id == execution_id)
                        )
                        exec_record = exec_result.scalar_one_or_none()
                        if exec_record and exec_record.project_id:
                            project_id = exec_record.project_id
                
                # 检查是否已迁移
                async with session_ctx() as session:
                    existing = await session.execute(
                        select(Report).where(Report.execution_id == execution_id)
                    )
                    if existing.scalar_one_or_none():
                        continue  # Already migrated
                    
                    report = Report(
                        execution_id=execution_id or '',
                        project_id=project_id,
                        summary=json.dumps(summary, ensure_ascii=False) if summary else None,
                        module_groups=None,
                        results=json.dumps(results, ensure_ascii=False) if results else None,
                    )
                    session.add(report)
                    await session.commit()
                    migrated_count += 1
        elif isinstance(history_data, dict):
            # history.json might be a dict with different structure
            print(f"  Unexpected history.json format (dict, expected list). Skipping file-based migration.")
        
        # Backup history.json
        bak_path = history_path.with_suffix('.json.bak')
        history_path.rename(bak_path)
        print(f"  Backed up history.json -> history.json.bak")
        print(f"  Migrated {migrated_count} report entries to database")
    else:
        print(f"  No history.json found at {history_path}, skipping.")
    
    # Step 4: Add project_id to Task records
    print("\n[Step 4/5] Updating Task records...")
    async with session_ctx() as session:
        result = await session.execute(select(Task).where(Task.project_id == 0))
        tasks = result.scalars().all()
        for task in tasks:
            task.project_id = legacy_project_id
        if tasks:
            await session.commit()
        print(f"  Updated {len(tasks)} Task records -> project_id={legacy_project_id}")
    
    # Step 5: Verify migration
    print("\n[Step 5/5] Verifying migration results...")
    async with session_ctx() as session:
        # Count TestCaseDefinition
        tcd_count = (await session.execute(select(TestCaseDefinition))).scalars().all()
        tcd_with_project = [t for t in tcd_count if t.project_id != 0]
        tcd_no_project = [t for t in tcd_count if t.project_id == 0]
        print(f"  TestCaseDefinition: {len(tcd_count)} total, {len(tcd_with_project)} with project_id, {len(tcd_no_project)} without project_id")
        
        # Count Reports
        report_count = (await session.execute(select(Report))).scalars().all()
        print(f"  Reports in database: {len(report_count)}")
        
        # Count Tasks
        task_count = (await session.execute(select(Task))).scalars().all()
        task_with_project = [t for t in task_count if t.project_id != 0]
        print(f"  Tasks: {len(task_count)} total, {len(task_with_project)} with project_id")
        
        # Count Executions
        exec_count = (await session.execute(select(Execution))).scalars().all()
        exec_with_project = [e for e in exec_count if e.project_id != 0]
        print(f"  Executions: {len(exec_count)} total, {len(exec_with_project)} with project_id")
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(migrate())