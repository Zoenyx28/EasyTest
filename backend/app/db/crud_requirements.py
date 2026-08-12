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
from app.domains.test_execution.models import ExecutionCase


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


def _apply_perspective(content: str, perspective: str) -> dict:
    """把某视角确认合并进 content JSON，返回 {content, status}。

    status：product+testing 两视角都确认 → confirmed；否则 partially_confirmed。
    """
    try:
        obj = json.loads(content) if content else {}
    except (json.JSONDecodeError, TypeError):
        obj = {}
    confirmations = dict(obj.get('confirmations') or {})
    confirmations[perspective] = True
    obj['confirmations'] = confirmations
    both = bool(confirmations.get('product') and confirmations.get('testing'))
    return {
        'content': json.dumps(obj, ensure_ascii=False),
        'status': 'confirmed' if both else 'partially_confirmed',
    }


async def update_asset(asset_id: int, **kwargs) -> dict | None:
    """Update a single asset. perspective（product/testing）用于双视角确认（#22）。"""
    perspective = kwargs.pop('perspective', None)
    async with session_ctx() as session:
        result = await session.execute(
            select(RequirementAsset).where(RequirementAsset.id == asset_id)
        )
        a = result.scalar_one_or_none()
        if a is None:
            return None
        if perspective is not None:
            merged = _apply_perspective(a.content or '', perspective)
            kwargs.update(merged)
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

        # Test gaps（#23）
        gaps_result = await session.execute(
            select(TestGap).where(TestGap.requirement_id == req_id).order_by(TestGap.id)
        )
        test_gaps = [_test_gap_to_dict(g) for g in gaps_result.scalars().all()]

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
            'test_gaps': test_gaps,
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


# ══════════════════════════════════════════════════════════
# 覆盖率 / 测试缺口（#23）—— 确定性计算（不调 LLM）
# ══════════════════════════════════════════════════════════

HIGH_RISK_CATEGORIES = {'Exception', 'Security', 'Concurrency', 'Dependency'}


def _asset_category(asset: RequirementAsset) -> str:
    try:
        c = json.loads(asset.content) if asset.content else {}
    except (json.JSONDecodeError, TypeError):
        c = {}
    return c.get('category', '') or ''


async def compute_coverage(req_id: int) -> dict:
    """确定性计算 7 层覆盖率（#23）。

    - requirement：存在分析资产 → 100
    - story / test_point / scenario / case：已双视角确认数 / 总数
    - automation：已绑定自动化用例数 / 全部用例数（CaseBinding 统计）
    - risk：高风险测试点（异常/安全/并发/依赖）已被场景覆盖的比例
    """
    async with session_ctx() as session:
        rows = (await session.execute(
            select(RequirementAsset).where(RequirementAsset.requirement_id == req_id)
        )).scalars().all()

        by_type: dict[str, list[RequirementAsset]] = {}
        for a in rows:
            by_type.setdefault(a.asset_type, []).append(a)

        stories = by_type.get('story', [])
        test_points = by_type.get('test_point', [])
        scenarios = by_type.get('scenario', [])
        cases = by_type.get('case', [])

        confirmed = lambda xs: [x for x in xs if x.status == 'confirmed']

        # automation：有绑定的用例数 / 全部用例数
        bound_case_ids = set()
        case_ids = [c.id for c in cases]
        if case_ids:
            br = await session.execute(
                select(CaseBinding.generated_case_id).where(
                    CaseBinding.generated_case_id.in_(case_ids))
            )
            bound_case_ids = set(br.scalars().all())

        # risk：高风险测试点被 ≥1 个场景覆盖的比例
        risk_tps = [t for t in test_points if _asset_category(t) in HIGH_RISK_CATEGORIES]
        risk_covered = sum(
            1 for t in risk_tps if any(s.parent_id == t.id for s in scenarios)
        )

    def pct(num: int, den: int) -> int:
        return round(num * 100 / den) if den else 0

    return {
        'requirement_coverage': 100 if by_type.get('analysis') else 0,
        'story_coverage': pct(len(confirmed(stories)), len(stories)),
        'test_point_coverage': pct(len(confirmed(test_points)), len(test_points)),
        'scenario_coverage': pct(len(confirmed(scenarios)), len(scenarios)),
        'case_coverage': pct(len(confirmed(cases)), len(cases)),
        'automation_coverage': pct(len(bound_case_ids), len(cases)),
        'risk_coverage': pct(risk_covered, len(risk_tps)) if risk_tps else 100,
    }


async def save_coverage_snapshot(req_id: int, values: dict, details: str = '') -> dict:
    """持久化一份覆盖率快照，返回该快照。"""
    async with session_ctx() as session:
        row = CoverageSnapshot(
            requirement_id=req_id,
            requirement_coverage=int(values.get('requirement_coverage') or 0),
            story_coverage=int(values.get('story_coverage') or 0),
            test_point_coverage=int(values.get('test_point_coverage') or 0),
            scenario_coverage=int(values.get('scenario_coverage') or 0),
            case_coverage=int(values.get('case_coverage') or 0),
            automation_coverage=int(values.get('automation_coverage') or 0),
            risk_coverage=int(values.get('risk_coverage') or 0),
            details=details[:8000],
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return {c.name: getattr(row, c.name, 0) for c in CoverageSnapshot.__table__.columns
                if c.name.endswith('_coverage')}


async def replace_test_gaps(req_id: int, gaps: list[dict]) -> list[dict]:
    """覆盖式重写该需求的测试缺口。"""
    async with session_ctx() as session:
        await session.execute(
            delete(TestGap).where(TestGap.requirement_id == req_id)
        )
        saved = []
        for g in gaps:
            row = TestGap(
                requirement_id=req_id,
                layer=g.get('layer', ''),
                description=g.get('description', ''),
                severity=g.get('severity', 'P1') or 'P1',
                status=g.get('status', 'open'),
                source_ref=g.get('source_ref', ''),
            )
            session.add(row)
            saved.append(row)
        await session.commit()
        return [_test_gap_to_dict(r) for r in saved]


async def list_test_gaps(req_id: int) -> list[dict]:
    async with session_ctx() as session:
        result = await session.execute(
            select(TestGap).where(TestGap.requirement_id == req_id).order_by(TestGap.id)
        )
        return [_test_gap_to_dict(r) for r in result.scalars().all()]


async def get_test_gap(gap_id: int) -> dict | None:
    async with session_ctx() as session:
        r = await session.get(TestGap, gap_id)
        return _test_gap_to_dict(r) if r else None


async def close_test_gap(gap_id: int) -> dict | None:
    async with session_ctx() as session:
        r = await session.get(TestGap, gap_id)
        if r is None:
            return None
        r.status = 'closed'
        r.closed_at = datetime.utcnow()
        await session.commit()
        await session.refresh(r)
        return _test_gap_to_dict(r)


def _test_gap_to_dict(g: TestGap) -> dict:
    return {
        'id': g.id, 'requirement_id': g.requirement_id, 'layer': g.layer,
        'description': g.description, 'severity': g.severity, 'status': g.status,
        'source_ref': g.source_ref,
        'created_at': g.created_at.isoformat() if g.created_at else '',
        'closed_at': g.closed_at.isoformat() if g.closed_at else '',
    }


async def derive_test_gaps(req_id: int, project_id: int = 0, branch_id: int = 0) -> list[dict]:
    """确定性推导 TestGap（P0/P1）+ 执行历史反哺，覆盖式落库。

    规则：
    - 未确认 Story → P1
    - 已确认 Story 未生成测试点 → P1
    - 未确认测试点 / 未生成场景的测试点 → P1
    - 未绑定自动化用例 → P1（automation）
    - 仍 pending 的 CRITICAL 信息缺口 → P0
    - 最近执行失败用例（ExecutionCase.status=failed）关联的用例 → P0（高风险，执行反哺）
    """
    async with session_ctx() as session:
        rows = (await session.execute(
            select(RequirementAsset).where(RequirementAsset.requirement_id == req_id)
        )).scalars().all()
        by_type: dict[str, list[RequirementAsset]] = {}
        for a in rows:
            by_type.setdefault(a.asset_type, []).append(a)

        stories = by_type.get('story', [])
        test_points = by_type.get('test_point', [])
        scenarios = by_type.get('scenario', [])
        cases = by_type.get('case', [])

        # 绑定集合：case_id → 已绑定
        case_ids = [c.id for c in cases]
        bound_ids: set[int] = set()
        if case_ids:
            br = await session.execute(
                select(CaseBinding.generated_case_id).where(
                    CaseBinding.generated_case_id.in_(case_ids))
            )
            bound_ids = set(br.scalars().all())

        # 执行历史反哺：最近一次失败执行 → 失败用例 uid → 绑定 case
        exec_feedback: dict[int, str] = {}  # case_id → 'exec:<execution_id>'
        if project_id and branch_id and case_ids:
            exec_result = await session.execute(
                select(Execution)
                .where(Execution.project_id == project_id,
                       Execution.branch_id == branch_id,
                       Execution.fail_count > 0)
                .order_by(desc(Execution.start_time)).limit(1)
            )
            latest_failed = exec_result.scalar_one_or_none()
            if latest_failed:
                ec_result = await session.execute(
                    select(ExecutionCase.uid).where(
                        ExecutionCase.execution_id == latest_failed.execution_id,
                        ExecutionCase.status == 'failed',
                    )
                )
                failed_uids = set(ec_result.scalars().all())
                if failed_uids:
                    bind_result = await session.execute(
                        select(CaseBinding.generated_case_id, CaseBinding.uid).where(
                            CaseBinding.generated_case_id.in_(case_ids))
                    )
                    for cid, uid in bind_result.all():
                        if uid in failed_uids:
                            exec_feedback[cid] = f'exec:{latest_failed.execution_id}'

        gaps: list[dict] = []
        # 未确认 Story → P1
        for s in stories:
            if s.status != 'confirmed':
                gaps.append({'layer': 'story', 'severity': 'P1',
                             'description': f'Story「{s.title[:40]}」未双视角确认',
                             'source_ref': f'story:{s.id}'})
        # 已确认 Story 无测试点 → P1
        confirmed_story_ids = {s.id for s in stories if s.status == 'confirmed'}
        covered_story_ids = {tp.story_id for tp in test_points if tp.story_id}
        for sid in confirmed_story_ids - covered_story_ids:
            gaps.append({'layer': 'test_point', 'severity': 'P1',
                         'description': '已确认 Story 尚未生成测试点', 'source_ref': f'story:{sid}'})
        # 未确认测试点 / 无场景 → P1
        for tp in test_points:
            if tp.status != 'confirmed':
                gaps.append({'layer': 'test_point', 'severity': 'P1',
                             'description': f'测试点「{tp.title[:40]}」未确认',
                             'source_ref': f'test_point:{tp.id}'})
            elif not any(sc.parent_id == tp.id for sc in scenarios):
                gaps.append({'layer': 'scenario', 'severity': 'P1',
                             'description': f'测试点「{tp.title[:40]}」未生成场景',
                             'source_ref': f'test_point:{tp.id}'})
        # 未绑定自动化用例 → P1；执行失败用例 → P0（反哺）
        for c in cases:
            if c.id not in bound_ids:
                gaps.append({'layer': 'automation', 'severity': 'P1',
                             'description': f'用例「{c.title[:40]}」未绑定自动化用例',
                             'source_ref': f'case:{c.id}'})
            elif c.id in exec_feedback:
                gaps.append({'layer': 'case', 'severity': 'P0',
                             'description': f'用例「{c.title[:40]}」最近执行失败，高风险未覆盖',
                             'source_ref': exec_feedback[c.id]})
        # CRITICAL 信息缺口 → P0
        for g in by_type.get('gap', []):
            if g.status == 'confirmed':
                continue
            try:
                gc = json.loads(g.content) if g.content else {}
            except (json.JSONDecodeError, TypeError):
                gc = {}
            if (g.gate_status or gc.get('severity', '')) in ('CRITICAL', 'P0'):
                gaps.append({'layer': 'information_gap', 'severity': 'P0',
                             'description': f'信息缺口「{g.title[:40]}」未确认（CRITICAL）',
                             'source_ref': f'gap:{g.id}'})

    await replace_test_gaps(req_id, gaps)
    return await list_test_gaps(req_id)
