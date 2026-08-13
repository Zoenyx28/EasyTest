"""CRUD operations for the Requirement Design domain."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select, desc, delete, update, func, and_

from app.shared.database import session_ctx
from app.domains.requirement_design.models import (
    Requirement, RequirementAsset, CaseBinding, AITask,
    ReviewAudit, CoverageSnapshot, TestGap,
)


# ── Requirement CRUD ──


async def create_requirement(
    project_id: int,
    branch_id: int,
    title: str,
    created_by: int,
    content: str = '',
    source_type: str = 'text',
    source_meta: str = '',
    priority: str = 'P2',
) -> dict:
    """Create a new requirement."""
    async with session_ctx() as session:
        req = Requirement(
            project_id=project_id,
            branch_id=branch_id,
            title=title,
            content=content,
            source_type=source_type,
            source_meta=source_meta,
            priority=priority,
            created_by=created_by,
        )
        session.add(req)
        await session.commit()
        await session.refresh(req)
        return _req_to_dict(req)


async def get_requirement(req_id: int) -> dict | None:
    """Get a single requirement by ID."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Requirement).where(Requirement.id == req_id)
        )
        req = result.scalar_one_or_none()
        return _req_to_dict(req) if req else None


async def list_requirements(
    project_id: int,
    branch_id: int,
    status: str = '',
    search: str = '',
    limit: int = 100,
) -> list[dict]:
    """List requirements for a project+branch, with optional filters."""
    async with session_ctx() as session:
        q = select(Requirement).where(
            Requirement.project_id == project_id,
            Requirement.branch_id == branch_id,
        )
        if status:
            q = q.where(Requirement.status == status)
        if search:
            q = q.where(Requirement.title.contains(search))
        q = q.order_by(desc(Requirement.updated_at)).limit(limit)
        result = await session.execute(q)
        return [_req_to_dict(r) for r in result.scalars().all()]


async def update_requirement(req_id: int, **kwargs) -> dict | None:
    """Update requirement fields."""
    async with session_ctx() as session:
        kwargs['updated_at'] = datetime.utcnow()
        await session.execute(
            update(Requirement).where(Requirement.id == req_id).values(**kwargs)
        )
        await session.commit()
        result = await session.execute(
            select(Requirement).where(Requirement.id == req_id)
        )
        req = result.scalar_one_or_none()
        return _req_to_dict(req) if req else None


async def delete_requirement(req_id: int) -> bool:
    """Delete a requirement and its assets."""
    async with session_ctx() as session:
        await session.execute(
            delete(RequirementAsset).where(RequirementAsset.requirement_id == req_id)
        )
        await session.execute(
            delete(Requirement).where(Requirement.id == req_id)
        )
        await session.commit()
        return True


# ── RequirementAsset CRUD ──


async def get_assets(
    requirement_id: int,
    asset_type: str = '',
) -> list[dict]:
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


async def get_asset(asset_id: int) -> dict | None:
    """Get a single asset by id."""
    async with session_ctx() as session:
        result = await session.execute(
            select(RequirementAsset).where(RequirementAsset.id == asset_id)
        )
        a = result.scalar_one_or_none()
        return _asset_to_dict(a) if a else None


async def upsert_assets(
    requirement_id: int,
    asset_type: str,
    items: list[dict],
    created_by: int = 0,
) -> list[dict]:
    """Replace all assets of a given type for a requirement with new items.

    This implements the overwrite pattern (ADR-0015): old assets of the same
    type are deleted, new ones are inserted.
    """
    async with session_ctx() as session:
        # Delete existing assets of this type
        await session.execute(
            delete(RequirementAsset).where(
                RequirementAsset.requirement_id == requirement_id,
                RequirementAsset.asset_type == asset_type,
            )
        )

        # Insert new assets
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


async def create_asset(requirement_id: int, asset_type: str, item: dict,
                       created_by: int = 0) -> dict:
    """Append a single asset（追加，不覆盖 —— 用于 AI 补测挂载，#23）。"""
    async with session_ctx() as session:
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
        await session.commit()
        await session.refresh(asset)
        return _asset_to_dict(asset)


async def update_asset(asset_id: int, **kwargs) -> dict | None:
    """Update a single asset's fields. perspective（product/testing）用于双视角确认（#22）。"""
    perspective = kwargs.pop('perspective', None)
    async with session_ctx() as session:
        result = await session.execute(
            select(RequirementAsset).where(RequirementAsset.id == asset_id)
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            return None
        if perspective is not None:
            try:
                obj = json.loads(asset.content) if asset.content else {}
            except (json.JSONDecodeError, TypeError):
                obj = {}
            confirmations = dict(obj.get('confirmations') or {})
            confirmations[perspective] = True
            obj['confirmations'] = confirmations
            kwargs['content'] = json.dumps(obj, ensure_ascii=False)
            both = bool(confirmations.get('product') and confirmations.get('testing'))
            kwargs['status'] = 'confirmed' if both else 'partially_confirmed'
        await session.execute(
            update(RequirementAsset).where(RequirementAsset.id == asset_id).values(**kwargs)
        )
        await session.commit()
        result = await session.execute(
            select(RequirementAsset).where(RequirementAsset.id == asset_id)
        )
        asset = result.scalar_one_or_none()
        return _asset_to_dict(asset) if asset else None


# ── Workbench aggregate query ──


async def get_workbench_data(req_id: int) -> dict | None:
    """Aggregate all data needed for the workbench in one call.

    Returns: requirement + all assets + ai_tasks + defect summary + execution summary.
    """
    async with session_ctx() as session:
        # Requirement
        req_result = await session.execute(
            select(Requirement).where(Requirement.id == req_id)
        )
        req = req_result.scalar_one_or_none()
        if not req:
            return None

        # All assets
        assets_result = await session.execute(
            select(RequirementAsset)
            .where(RequirementAsset.requirement_id == req_id)
            .order_by(RequirementAsset.sort_order, RequirementAsset.id)
        )
        assets = [_asset_to_dict(a) for a in assets_result.scalars().all()]

        # AI Tasks
        tasks_result = await session.execute(
            select(AITask)
            .where(AITask.requirement_id == req_id)
            .order_by(desc(AITask.updated_at))
        )
        ai_tasks = [_aitask_to_dict(t) for t in tasks_result.scalars().all()]

        # Defect summary (from defect_tracking models)
        from app.domains.defect_tracking.models import Defect
        defect_count_result = await session.execute(
            select(func.count(Defect.id)).where(Defect.requirement_id == req_id)
        )
        defect_count = defect_count_result.scalar() or 0

        open_defect_count_result = await session.execute(
            select(func.count(Defect.id)).where(
                Defect.requirement_id == req_id,
                Defect.status.notin_(['closed', 'resolved']),
            )
        )
        open_defect_count = open_defect_count_result.scalar() or 0

        # Recent defects
        defects_result = await session.execute(
            select(Defect)
            .where(Defect.requirement_id == req_id)
            .order_by(desc(Defect.updated_at))
            .limit(5)
        )
        defects = []
        for d in defects_result.scalars().all():
            defects.append({
                'id': d.id,
                'title': d.title,
                'severity': d.severity,
                'priority': d.priority,
                'status': d.status,
                'assignee_id': d.assignee_id,
                'creator_id': d.creator_id,
                'case_uid': d.case_uid,
                'created_at': d.created_at.isoformat() if d.created_at else '',
                'updated_at': d.updated_at.isoformat() if d.updated_at else '',
            })

        # Execution summary
        from app.domains.test_execution.models import Execution, ExecutionCase
        latest_exec_result = await session.execute(
            select(Execution)
            .where(Execution.project_id == req.project_id,
                   Execution.branch_id == req.branch_id)
            .order_by(desc(Execution.start_time))
            .limit(1)
        )
        latest_exec = latest_exec_result.scalar_one_or_none()
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
            select(CoverageSnapshot)
            .where(CoverageSnapshot.requirement_id == req_id)
            .order_by(desc(CoverageSnapshot.created_at))
            .limit(1)
        )
        cov = cov_result.scalar_one_or_none()
        coverage = None
        if cov:
            coverage = {
                'requirement_coverage': cov.requirement_coverage,
                'story_coverage': cov.story_coverage,
                'test_point_coverage': cov.test_point_coverage,
                'scenario_coverage': cov.scenario_coverage,
                'case_coverage': cov.case_coverage,
                'automation_coverage': cov.automation_coverage,
                'risk_coverage': cov.risk_coverage,
            }

        # Case bindings
        bindings_result = await session.execute(
            select(CaseBinding).where(
                CaseBinding.generated_case_id.in_(
                    [a['id'] for a in assets if a['asset_type'] == 'case']
                )
            )
        )
        bindings = []
        for b in bindings_result.scalars().all():
            bindings.append({
                'id': b.id,
                'generated_case_id': b.generated_case_id,
                'uid': b.uid,
                'project_id': b.project_id,
                'branch_id': b.branch_id,
            })

        return {
            'requirement': _req_to_dict(req),
            'assets': assets,
            'ai_tasks': ai_tasks,
            'defect_count': defect_count,
            'open_defect_count': open_defect_count,
            'defects': defects,
            'execution_summary': exec_summary,
            'coverage': coverage,
            'bindings': bindings,
        }


# ── CaseBinding CRUD ──


async def create_binding(generated_case_id: int, uid: str, project_id: int, branch_id: int) -> dict:
    """Bind a generated case to a test case definition."""
    async with session_ctx() as session:
        b = CaseBinding(
            generated_case_id=generated_case_id,
            uid=uid,
            project_id=project_id,
            branch_id=branch_id,
        )
        session.add(b)
        await session.commit()
        await session.refresh(b)
        return {
            'id': b.id,
            'generated_case_id': b.generated_case_id,
            'uid': b.uid,
            'project_id': b.project_id,
            'branch_id': b.branch_id,
        }


async def delete_binding(binding_id: int) -> bool:
    """Remove a case binding."""
    async with session_ctx() as session:
        await session.execute(
            delete(CaseBinding).where(CaseBinding.id == binding_id)
        )
        await session.commit()
        return True


async def get_bindings_for_case(generated_case_id: int) -> list[dict]:
    """Get all bindings for a generated case."""
    async with session_ctx() as session:
        result = await session.execute(
            select(CaseBinding).where(CaseBinding.generated_case_id == generated_case_id)
        )
        bindings = result.scalars().all()
        return [{
            'id': b.id, 'generated_case_id': b.generated_case_id,
            'uid': b.uid, 'project_id': b.project_id, 'branch_id': b.branch_id,
        } for b in bindings]


# ── AITask CRUD ──


async def create_ai_task(requirement_id: int, stage: str, created_by: int = 0,
                         model: str = '', prompt_version: str = '') -> dict:
    """Create a new AI task record."""
    async with session_ctx() as session:
        task = AITask(
            requirement_id=requirement_id,
            stage=stage,
            status='PENDING',
            model=model,
            prompt_version=prompt_version,
            created_by=created_by,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return _aitask_to_dict(task)


async def update_ai_task(task_id: int, **kwargs) -> dict | None:
    """Update AI task status."""
    async with session_ctx() as session:
        kwargs['updated_at'] = datetime.utcnow()
        await session.execute(
            update(AITask).where(AITask.id == task_id).values(**kwargs)
        )
        await session.commit()
        result = await session.execute(select(AITask).where(AITask.id == task_id))
        task = result.scalar_one_or_none()
        return _aitask_to_dict(task) if task else None


async def get_ai_tasks(requirement_id: int, stage: str = '') -> list[dict]:
    """Get AI tasks for a requirement."""
    async with session_ctx() as session:
        q = select(AITask).where(AITask.requirement_id == requirement_id)
        if stage:
            q = q.where(AITask.stage == stage)
        q = q.order_by(desc(AITask.updated_at))
        result = await session.execute(q)
        return [_aitask_to_dict(t) for t in result.scalars().all()]


async def create_review_audit(artifact_type: str, artifact_id: int, score: int,
                              dimension_scores: str = '', issues: str = '',
                              suggestions: str = '', information_gaps: str = '',
                              gate_status: str = '', model: str = '',
                              prompt_version: str = '', user_id: int = 0) -> dict:
    """Write an AI review audit record (append-only)."""
    async with session_ctx() as session:
        row = ReviewAudit(
            artifact_type=artifact_type, artifact_id=artifact_id, score=score,
            dimension_scores=dimension_scores, issues=issues, suggestions=suggestions,
            information_gaps=information_gaps, gate_status=gate_status,
            model=model, prompt_version=prompt_version, created_by=user_id,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return {'id': row.id, 'artifact_type': row.artifact_type,
                'artifact_id': row.artifact_id, 'score': row.score,
                'gate_status': row.gate_status}


# ── Serialization helpers ──


def _req_to_dict(req: Requirement) -> dict:
    return {
        'id': req.id,
        'project_id': req.project_id,
        'branch_id': req.branch_id,
        'title': req.title,
        'content': req.content,
        'source_type': req.source_type,
        'source_meta': req.source_meta,
        'priority': req.priority,
        'status': req.status,
        'created_by': req.created_by,
        'created_at': req.created_at.isoformat() if req.created_at else '',
        'updated_at': req.updated_at.isoformat() if req.updated_at else '',
    }


def _asset_to_dict(a: RequirementAsset) -> dict:
    return {
        'id': a.id,
        'requirement_id': a.requirement_id,
        'asset_type': a.asset_type,
        'parent_id': a.parent_id,
        'story_id': a.story_id,
        'title': a.title,
        'description': a.description,
        'content': a.content,
        'score': a.score,
        'gate_status': a.gate_status,
        'review_comment': a.review_comment,
        'sort_order': a.sort_order,
        'status': a.status,
        'created_by': a.created_by,
        'created_at': a.created_at.isoformat() if a.created_at else '',
    }


def _aitask_to_dict(t: AITask) -> dict:
    return {
        'id': t.id,
        'requirement_id': t.requirement_id,
        'stage': t.stage,
        'status': t.status,
        'error': t.error,
        'model': t.model,
        'prompt_version': t.prompt_version,
        'created_by': t.created_by,
        'created_at': t.created_at.isoformat() if t.created_at else '',
        'updated_at': t.updated_at.isoformat() if t.updated_at else '',
    }
