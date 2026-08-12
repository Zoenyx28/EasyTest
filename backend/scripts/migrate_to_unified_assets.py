#!/usr/bin/env python3
"""Migrate legacy 12 layered tables into the unified requirement_assets table.

Mapping (legacy table → asset_type):
  requirement_analyses  → analysis
  requirement_reviews   → story_review
  stories               → story
  test_points           → test_point
  test_point_reviews    → test_point_review
  test_scenarios        → scenario
  scenario_reviews      → scenario_review
  generated_cases       → case
  case_reviews          → case_review
  test_strategies       → strategy
  review_audits         → audit
  information_gaps      → gap

Tables NOT migrated (self-regenerating):
  - coverage_snapshots  (regenerated on demand)
  - test_gaps           (regenerated on demand)
  - case_bindings       (has own dedicated table, kept as-is)

Idempotent: skips if requirement_assets already contains data for the requirement.
Run via:  PYTHONPATH=. python3 scripts/migrate_to_unified_assets.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime

sys.path.insert(0, '.')

from sqlalchemy import select, func, text

from app.db.database import session_ctx
from app.domains.requirement_design.models import RequirementAsset

# ── Legacy table imports (re-exported through app.db.models) ──
from app.domains.requirement_design.models import (
    RequirementAnalysis, RequirementReview, Story,
    TestPoint, TestPointReview, TestScenario,
    ScenarioReview, GeneratedCase, CaseReview,
    TestStrategy, ReviewAudit, InformationGap,
)


async def asset_count(requirement_id: int) -> int:
    """Check if assets already exist for a requirement."""
    async with session_ctx() as session:
        result = await session.execute(
            select(func.count(RequirementAsset.id)).where(
                RequirementAsset.requirement_id == requirement_id,
            ),
        )
        return result.scalar() or 0


async def migrate_analysis():
    """requirement_analyses → asset_type='analysis'."""
    async with session_ctx() as session:
        result = await session.execute(select(RequirementAnalysis))
        rows = result.scalars().all()

    migrated = 0
    for r in rows:
        if await asset_count(r.requirement_id) > 0:
            # Already has assets — skip if analysis already exists
            continue

        async with session_ctx() as session:
            asset = RequirementAsset(
                requirement_id=r.requirement_id,
                asset_type='analysis',
                parent_id=0,
                story_id=0,
                title='需求分析',
                description='AI 需求分析结果',
                content=r.elements or '{}',
                score=r.score or 0,
                gate_status='',
                review_comment='',
                sort_order=0,
                status='generated',
                created_by=r.created_by or 0,
                created_at=r.created_at or datetime.utcnow(),
            )
            session.add(asset)
            await session.commit()
            migrated += 1

    print(f'  [analysis] migrated {migrated} rows from requirement_analyses')
    return migrated


async def migrate_stories():
    """stories → asset_type='story'."""
    async with session_ctx() as session:
        result = await session.execute(select(Story))
        rows = result.scalars().all()

    migrated = 0
    for r in rows:
        if await asset_count(r.requirement_id) > 0:
            uploaded = 0
            async with session_ctx() as session:
                result = await session.execute(
                    select(func.count(RequirementAsset.id)).where(
                        RequirementAsset.requirement_id == r.requirement_id,
                        RequirementAsset.asset_type == 'story',
                    ),
                )
                uploaded = result.scalar() or 0
            if uploaded > 0:
                continue

        content = json.dumps({
            'acceptance_criteria': r.acceptance_criteria or '',
            'dimension_scores': r.dimension_scores or '',
            'dependencies': r.dependencies or '',
        }, ensure_ascii=False)

        async with session_ctx() as session:
            asset = RequirementAsset(
                requirement_id=r.requirement_id,
                asset_type='story',
                parent_id=0,
                story_id=0,
                title=r.title,
                description=r.description or '',
                content=content,
                score=r.score or 0,
                gate_status=r.gate_status or '',
                review_comment=r.score_reason or '',
                sort_order=r.sort_order or 0,
                status='generated',
                created_by=0,
                created_at=r.created_at or datetime.utcnow(),
            )
            session.add(asset)
            await session.commit()
            migrated += 1

    print(f'  [story] migrated {migrated} rows from stories')
    return migrated


async def migrate_test_points():
    """test_points → asset_type='test_point'."""
    async with session_ctx() as session:
        result = await session.execute(select(TestPoint))
        rows = result.scalars().all()

    migrated = 0
    for r in rows:
        content = json.dumps({
            'category': r.category or 'Functional',
            'story_id': r.story_id or 0,
        }, ensure_ascii=False)

        async with session_ctx() as session:
            asset = RequirementAsset(
                requirement_id=r.requirement_id,
                asset_type='test_point',
                parent_id=r.parent_id or 0,
                story_id=r.story_id or 0,
                title=r.title,
                description=r.description or '',
                content=content,
                score=0,
                gate_status='',
                review_comment='',
                sort_order=r.sort_order or 0,
                status=r.status or 'generated',
                created_by=0,
                created_at=r.created_at or datetime.utcnow(),
            )
            session.add(asset)
            await session.commit()
            migrated += 1

    print(f'  [test_point] migrated {migrated} rows from test_points')
    return migrated


async def migrate_scenarios():
    """test_scenarios → asset_type='scenario'."""
    async with session_ctx() as session:
        result = await session.execute(select(TestScenario))
        rows = result.scalars().all()

    migrated = 0
    for r in rows:
        content = json.dumps({
            'coverage_dim': r.coverage_dim or '',
            'test_point_id': r.test_point_id or 0,
        }, ensure_ascii=False)

        async with session_ctx() as session:
            asset = RequirementAsset(
                requirement_id=r.requirement_id,
                asset_type='scenario',
                parent_id=r.test_point_id or 0,
                story_id=0,
                title=r.title,
                description=r.description or '',
                content=content,
                score=0,
                gate_status='',
                review_comment='',
                sort_order=r.sort_order or 0,
                status='generated',
                created_by=0,
                created_at=r.created_at or datetime.utcnow(),
            )
            session.add(asset)
            await session.commit()
            migrated += 1

    print(f'  [scenario] migrated {migrated} rows from test_scenarios')
    return migrated


async def migrate_cases():
    """generated_cases → asset_type='case'."""
    async with session_ctx() as session:
        result = await session.execute(select(GeneratedCase))
        rows = result.scalars().all()

    migrated = 0
    for r in rows:
        content = json.dumps({
            'preconditions': r.preconditions or '',
            'steps': r.steps or '',
            'expected': r.expected or '',
            'score_reason': r.score_reason or '',
        }, ensure_ascii=False)

        async with session_ctx() as session:
            asset = RequirementAsset(
                requirement_id=r.requirement_id,
                asset_type='case',
                parent_id=0,
                story_id=r.story_id or 0,
                title=r.title,
                description='',
                content=content,
                score=r.score or 0,
                gate_status=r.gate_status or '',
                review_comment='',
                sort_order=0,
                status='generated',
                created_by=0,
                created_at=r.created_at or datetime.utcnow(),
            )
            session.add(asset)
            await session.commit()
            migrated += 1

    print(f'  [case] migrated {migrated} rows from generated_cases')
    return migrated


async def migrate_review(table_cls, asset_type: str, label: str) -> int:
    """Generic review table → asset for the given asset_type."""
    async with session_ctx() as session:
        result = await session.execute(select(table_cls))
        rows = result.scalars().all()

    migrated = 0
    for r in rows:
        content = {}
        for attr in ['dimension_scores', 'coverage', 'issues', 'suggestions',
                      'checks', 'risks', 'conclusion', 'result', 'elements',
                      'information_gaps']:
            val = getattr(r, attr, None)
            if val:
                content[attr] = val

        async with session_ctx() as session:
            asset = RequirementAsset(
                requirement_id=r.requirement_id,
                asset_type=asset_type,
                parent_id=0,
                story_id=0,
                title=f'{label} (ID={r.id})',
                description='',
                content=json.dumps(content, ensure_ascii=False),
                score=getattr(r, 'score', 0) or 0,
                gate_status=getattr(r, 'gate_status', '') or '',
                review_comment=getattr(r, 'review_comment', '') or '',
                sort_order=0,
                status='generated',
                created_by=getattr(r, 'created_by', 0) or 0,
                created_at=getattr(r, 'created_at', datetime.utcnow()) or datetime.utcnow(),
            )
            session.add(asset)
            await session.commit()
            migrated += 1

    print(f'  [{asset_type}] migrated {migrated} rows from {table_cls.__tablename__}')
    return migrated


async def migrate_gaps():
    """information_gaps → asset_type='gap'."""
    async with session_ctx() as session:
        result = await session.execute(select(InformationGap))
        rows = result.scalars().all()

    migrated = 0
    for r in rows:
        content = json.dumps({
            'gap_type': r.gap_type or '',
            'severity': r.severity or 'HIGH',
            'question': r.question or '',
            'status': r.status or 'pending',
            'confirmed_by': r.confirmed_by or 0,
            'confirmed_at': r.confirmed_at.isoformat() if r.confirmed_at else None,
        }, ensure_ascii=False)

        async with session_ctx() as session:
            asset = RequirementAsset(
                requirement_id=r.requirement_id,
                asset_type='gap',
                parent_id=0,
                story_id=r.story_id or 0,
                title=r.gap_type or '信息缺口',
                description=r.description or '',
                content=content,
                score=0,
                gate_status=r.severity or 'HIGH',
                review_comment='',
                sort_order=0,
                status=r.status or 'pending',
                created_by=0,
                created_at=r.created_at or datetime.utcnow(),
            )
            session.add(asset)
            await session.commit()
            migrated += 1

    print(f'  [gap] migrated {migrated} rows from information_gaps')
    return migrated


async def main():
    print('=== 数据迁移：旧分层表 → requirement_assets ===')
    total = 0

    # 1. requirement_analyses → analysis
    total += await migrate_analysis()

    # 2. requirement_reviews → story_review
    total += await migrate_review(RequirementReview, 'story_review', '需求评审')

    # 3. stories → story
    total += await migrate_stories()

    # 4. test_points → test_point
    total += await migrate_test_points()

    # 5. test_point_reviews → test_point_review
    total += await migrate_review(TestPointReview, 'test_point_review', '测试点评审')

    # 6. test_scenarios → scenario
    total += await migrate_scenarios()

    # 7. scenario_reviews → scenario_review
    total += await migrate_review(ScenarioReview, 'scenario_review', '场景评审')

    # 8. generated_cases → case
    total += await migrate_cases()

    # 9. case_reviews → case_review
    total += await migrate_review(CaseReview, 'case_review', '用例评审')

    # 10. test_strategies → strategy
    total += await migrate_review(TestStrategy, 'strategy', '测试策略')

    # 11. review_audits → audit
    total += await migrate_review(ReviewAudit, 'audit', '评审审计')

    # 12. information_gaps → gap
    total += await migrate_gaps()

    print(f'\n=== 迁移完成：共迁移 {total} 条记录到 requirement_assets ===')

    # Print summary
    async with session_ctx() as session:
        result = await session.execute(
            select(RequirementAsset.asset_type, func.count(RequirementAsset.id))
            .group_by(RequirementAsset.asset_type)
        )
        print('\n当前 requirement_assets 统计：')
        for asset_type, count in result.all():
            print(f'  {asset_type}: {count}')


if __name__ == '__main__':
    asyncio.run(main())
