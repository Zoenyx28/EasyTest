"""ADR-0016: Requirement workbench CRUD — unified asset table + workbench aggregate."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, desc, delete, update, func, and_

from .database import session_ctx
from .models import (
    Requirement, RequirementAsset, AITask, CaseBinding,
    ReviewAudit, CoverageSnapshot, TestGap,
    Defect, Execution,
)


# ── Requirement CRUD (extended) ──


async def get_requirement_with_stats(req_id: int) -> dict | None:
    """Get a requirement with aggregated statistics."""
    async with session_ctx() as session:
        r = await session.get(Requirement, req_id)
        if not r:
            return None

        # Count assets by type
        asset_counts = {}
        for atype in ['analysis', 'story', 'test_point', 'scenario', 'case']:
            count_result = await session.execute(
                select(func.count(RequirementAsset.id)).where(
                    RequirementAsset.requirement_id == req_id,
                    RequirementAsset.asset_type == atype,
                )
            )
            asset_counts[atype] = count_result.scalar() or 0

        # Defect counts
        defect_count = (await session.execute(
            select(func.count(Defect.id)).where(Defect.requirement_id == req_id)
        )).scalar() or 0
        open_defect_count = (await session.execute(
            select(func.count(Defect.id)).where(
                Defect.requirement_id == req_id,
                Defect.status.notin_(['closed', 'resolved']),
            )
        )).scalar() or 0

        return {
            'id': r.id,
            'project_id': r.project_id,
            'branch_id': r.branch_id,
            'title': r.title,
            'summary': r.summary,
            'content': getattr(r, 'content', ''),
            'source_type': getattr(r, 'source_type', 'text'),
            'source_meta': getattr(r, 'source_meta', ''),
            'priority': r.priority,
            'status': r.status,
            'created_by': r.created_by,
            'created_at': r.created_at.isoformat() if r.created_at else '',
            'updated_at': r.updated_at.isoformat() if r.updated_at else '',
            'asset_counts': asset_counts,
            'defect_count': defect_count,
            'open_defect_count': open_defect_count,
        }


# ── RequirementAsset CRUD ──


async def get_assets(requirement_id: int, asset_type: str = '') -> list[dict]:
    """Get all assets for a requirement, optionally filtered by type."""
    async with session_ctx() as session:
        q = select(RequirementAsset).where(
            RequirementAsset.requirement_id == requirement_id
        )
        if asset_type:
            q = q.where(RequirementAsset.asset_type == asset_type)
        q = q.order_by(RequirementAsset.sort_order, RequirementAsset.id)
        result = await session.execute(q)
        return [_asset_to_dict(a) for a in result.scalars().all()]


async def upsert_assets(
    requirement_id: int,
    asset_type: str,
    items: list[dict],
    created_by: int = 0,
) -> list[dict]:
    """Replace all assets of given type (overwrite pattern per ADR-0015)."""
    async with session_ctx() as session:
        await session.execute(
            delete(RequirementAsset).where(
                RequirementAsset.requirement_id == requirement_id,
                RequirementAsset.asset_type == asset_type,
            )
        )
        new_assets = []
        for item in items:
            asset = RequirementAsset(
                requirement_id=requirement_id,
                asset_type=asset_type,
                parent_id=item.get('parent_id', 0),
                story_id=item.get('story_id', 0),
                title=item.get('title', ''),
                description=item.get('description', ''),
                content=item.get('content', ''),
                score=item.get('score', 0),
                gate_status=item.get('gate_status', ''),
                review_comment=item.get('review_comment', ''),
                sort_order=item.get('sort_order', 0),
                status=item.get('status', 'generated'),
                created_by=created_by,
            )
            session.add(asset)
            new_assets.append(asset)
        await session.commit()
        for a in new_assets:
            await session.refresh(a)
        return [_asset_to_dict(a) for a in new_assets]


async def update_asset(asset_id: int, **kwargs) -> dict | None:
    """Update a single asset."""
    async with session_ctx() as session:
        await session.execute(
            update(RequirementAsset).where(RequirementAsset.id == asset_id).values(**kwargs)
        )
        await session.commit()
        result = await session.execute(
            select(RequirementAsset).where(RequirementAsset.id == asset_id)
        )
        a = result.scalar_one_or_none()
        return _asset_to_dict(a) if a else None


# ── Workbench aggregate ──


async def get_workbench_data(req_id: int, project_id: int = 0, branch_id: int = 0) -> dict | None:
    """Get all data needed for the workbench in one call."""
    async with session_ctx() as session:
        r = await session.get(Requirement, req_id)
        if not r:
            return None

        # All assets
        assets_result = await session.execute(
            select(RequirementAsset)
            .where(RequirementAsset.requirement_id == req_id)
            .order_by(RequirementAsset.asset_type, RequirementAsset.sort_order, RequirementAsset.id)
        )
        assets = [_asset_to_dict(a) for a in assets_result.scalars().all()]

        # AI Tasks
        tasks_result = await session.execute(
            select(AITask).where(AITask.requirement_id == req_id)
            .order_by(desc(AITask.updated_at)).limit(10)
        )
        ai_tasks = [_aitask_to_dict(t) for t in tasks_result.scalars().all()]

        # Defects
        defects_result = await session.execute(
            select(Defect).where(Defect.requirement_id == req_id)
            .order_by(desc(Defect.updated_at)).limit(10)
        )
        defects = []
        for d in defects_result.scalars().all():
            defects.append({
                'id': d.id, 'title': d.title, 'severity': d.severity,
                'priority': d.priority, 'status': d.status,
                'assignee_id': d.assignee_id, 'creator_id': d.creator_id,
                'case_uid': d.case_uid, 'requirement_id': getattr(d, 'requirement_id', 0),
                'created_at': d.created_at.isoformat() if d.created_at else '',
                'updated_at': d.updated_at.isoformat() if d.updated_at else '',
            })
        defect_count = len(defects_result.scalars().all())
        open_count_result = await session.execute(
            select(func.count(Defect.id)).where(
                Defect.requirement_id == req_id,
                Defect.status.notin_(['closed', 'resolved']),
            )
        )
        open_defect_count = open_count_result.scalar() or 0

        # Case bindings (for case-type assets)
        case_asset_ids = [a['id'] for a in assets if a['asset_type'] == 'case']
        bindings = []
        if case_asset_ids:
            bind_result = await session.execute(
                select(CaseBinding).where(CaseBinding.generated_case_id.in_(case_asset_ids))
            )
            for b in bind_result.scalars().all():
                bindings.append({
                    'id': b.id, 'generated_case_id': b.generated_case_id,
                    'uid': b.uid, 'project_id': b.project_id, 'branch_id': b.branch_id,
                })

        # Execution summary
        pid = project_id or r.project_id
        bid = branch_id or r.branch_id
        exec_result = await session.execute(
            select(Execution).where(
                Execution.project_id == pid, Execution.branch_id == bid,
            ).order_by(desc(Execution.start_time)).limit(1)
        )
        latest_exec = exec_result.scalar_one_or_none()
        exec_summary = None
        if latest_exec:
            exec_summary = {
                'execution_id': latest_exec.execution_id,
                'status': latest_exec.status,
                'total_count': latest_exec.total_count,
                'success_count': latest_exec.success_count,
                'fail_count': latest_exec.fail_count,
                'start_time': latest_exec.start_time.isoformat() if latest_exec.start_time else '',
                'end_time': latest_exec.end_time.isoformat() if latest_exec.end_time else '',
            }

        # Coverage
        cov_result = await session.execute(
            select(CoverageSnapshot).where(CoverageSnapshot.requirement_id == req_id)
            .order_by(desc(CoverageSnapshot.created_at)).limit(1)
        )
        cov = cov_result.scalar_one_or_none()
        coverage = None
        if cov:
            coverage = {c.name: getattr(cov, c.name, 0) for c in CoverageSnapshot.__table__.columns
                       if c.name.endswith('_coverage')}

        return {
            'requirement': {
                'id': r.id, 'project_id': r.project_id, 'branch_id': r.branch_id,
                'title': r.title, 'summary': r.summary,
                'content': getattr(r, 'content', ''),
                'source_type': getattr(r, 'source_type', 'text'),
                'source_meta': getattr(r, 'source_meta', ''),
                'priority': r.priority, 'status': r.status,
                'created_by': r.created_by,
                'created_at': r.created_at.isoformat() if r.created_at else '',
                'updated_at': r.updated_at.isoformat() if r.updated_at else '',
            },
            'assets': assets,
            'ai_tasks': ai_tasks,
            'defects': defects,
            'defect_count': defect_count,
            'open_defect_count': open_defect_count,
            'execution_summary': exec_summary,
            'coverage': coverage,
            'bindings': bindings,
        }


# ── CaseBinding ──


async def create_binding(generated_case_id: int, uid: str, project_id: int, branch_id: int) -> dict:
    async with session_ctx() as session:
        b = CaseBinding(generated_case_id=generated_case_id, uid=uid, project_id=project_id, branch_id=branch_id)
        session.add(b)
        await session.commit()
        await session.refresh(b)
        return {'id': b.id, 'generated_case_id': b.generated_case_id, 'uid': b.uid,
                'project_id': b.project_id, 'branch_id': b.branch_id}


async def delete_binding(binding_id: int) -> bool:
    async with session_ctx() as session:
        await session.execute(delete(CaseBinding).where(CaseBinding.id == binding_id))
        await session.commit()
        return True


async def get_bindings_for_case(generated_case_id: int) -> list[dict]:
    async with session_ctx() as session:
        result = await session.execute(
            select(CaseBinding).where(CaseBinding.generated_case_id == generated_case_id)
        )
        return [{'id': b.id, 'generated_case_id': b.generated_case_id, 'uid': b.uid,
                 'project_id': b.project_id, 'branch_id': b.branch_id} for b in result.scalars().all()]


# ── AI Task helpers ──


async def create_ai_task(requirement_id: int, stage: str, created_by: int = 0,
                         model: str = '', prompt_version: str = '') -> dict:
    async with session_ctx() as session:
        t = AITask(requirement_id=requirement_id, stage=stage, status='PENDING',
                   model=model, prompt_version=prompt_version, created_by=created_by)
        session.add(t)
        await session.commit()
        await session.refresh(t)
        return _aitask_to_dict(t)


async def update_ai_task(task_id: int, **kwargs) -> dict | None:
    async with session_ctx() as session:
        kwargs['updated_at'] = datetime.utcnow()
        await session.execute(update(AITask).where(AITask.id == task_id).values(**kwargs))
        await session.commit()
        result = await session.execute(select(AITask).where(AITask.id == task_id))
        t = result.scalar_one_or_none()
        return _aitask_to_dict(t) if t else None


# ── Serialization ──


def _asset_to_dict(a: RequirementAsset) -> dict:
    return {
        'id': a.id, 'requirement_id': a.requirement_id,
        'asset_type': a.asset_type, 'parent_id': a.parent_id, 'story_id': a.story_id,
        'title': a.title, 'description': a.description, 'content': a.content,
        'score': a.score, 'gate_status': a.gate_status, 'review_comment': a.review_comment,
        'sort_order': a.sort_order, 'status': a.status, 'created_by': a.created_by,
        'created_at': a.created_at.isoformat() if a.created_at else '',
    }


def _aitask_to_dict(t: AITask) -> dict:
    return {
        'id': t.id, 'requirement_id': t.requirement_id, 'stage': t.stage,
        'status': t.status, 'error': t.error,
        'model': t.model, 'prompt_version': t.prompt_version, 'created_by': t.created_by,
        'created_at': t.created_at.isoformat() if t.created_at else '',
        'updated_at': t.updated_at.isoformat() if t.updated_at else '',
    }
