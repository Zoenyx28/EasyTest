"""CRUD operations for test execution records and discovery cache."""
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select, desc, delete, case, update

from .database import session_ctx
from .models import Branch, TestCaseDefinition, User
from .models import Task, TaskCase, Execution, ExecutionCase
from .models import Project, ProjectCase, Report, ProjectMember
from .models import DefectModule, Defect, DefectAttachment, DefectLog, DefectComment, ProjectNote
from .models import UserActiveProject


# ── Time / duration helpers ──

_TZ_CN = timezone(timedelta(hours=8))  # UTC+8 (Asia/Shanghai)


def dt_iso(dt: datetime | None) -> str:
    """Serialize a naive-UTC datetime as a GMT+8 ISO string (e.g. 2026-08-05T14:29:15+08:00).

    Timestamps are stored as naive UTC (datetime.utcnow), so API responses must
    be shifted to the local timezone (+08:00) before being returned to clients.
    """
    if not dt:
        return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ_CN).isoformat()


def dt_iso_from_str(s: str | None) -> str:
    """Parse an ISO string (stored naive UTC) and re-emit with GMT+8 offset.

    Used for VARCHAR timestamp columns (e.g. resolved_date) that are persisted
    as naive-UTC strings but must be returned with the timezone offset.
    """
    if not s:
        return ''
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return s
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ_CN).isoformat()


def fmt_duration_ms(ms: float | int | None) -> str:
    """Format a millisecond duration like the report generator (5ms / 1.5s / 2m5s)."""
    ms = int(ms or 0)
    if ms < 1000:
        return f'{ms}ms'
    if ms < 60000:
        return f'{ms / 1000:.1f}s'
    m = ms // 60000
    s = (ms % 60000) / 1000
    return f'{m}m{s:.0f}s'


def duration_between(start: datetime | None, end: datetime | None) -> str:
    """Human-readable duration between two naive-UTC timestamps."""
    if not start:
        return ''
    end = end or datetime.utcnow()
    return fmt_duration_ms((end - start).total_seconds() * 1000)


# ── Branch CRUD ──


async def create_branch(project_id: int, name: str, source_branch_id: int | None = None) -> int:
    """Create a branch for a project.

    If source_branch_id is provided, deep-copy TestCaseDefinitions from that branch.
    Returns the new branch id.
    """
    async with session_ctx() as session:
        # Get source_path/test_path from project or source branch
        project_result = await session.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if project is None:
            raise ValueError(f'Project {project_id} not found')

        source_path = project.server_path
        test_path = project.test_path

        is_empty = source_branch_id is None

        branch = Branch(
            project_id=project_id,
            name=name,
            source_branch_id=source_branch_id,
            is_default=False,
            is_empty=is_empty,
            source_path=source_path,
            test_path=test_path,
        )
        session.add(branch)
        await session.flush()
        branch_id = branch.id

        # Deep-copy TestCaseDefinitions from source branch
        if source_branch_id:
            source_cases = await session.execute(
                select(TestCaseDefinition).where(
                    TestCaseDefinition.project_id == project_id,
                    TestCaseDefinition.branch_id == source_branch_id,
                )
            )
            for sc in source_cases.scalars().all():
                new_case = TestCaseDefinition(
                    uid=sc.uid,
                    project_id=project_id,
                    branch_id=branch_id,
                    name=sc.name,
                    method_name=sc.method_name,
                    class_name=sc.class_name,
                    module=sc.module,
                    full_name=sc.full_name,
                    description=sc.description,
                    tags=sc.tags,
                    updated_at=datetime.utcnow(),
                    is_new=sc.is_new,
                    test_type=sc.test_type,
                    file_path=sc.file_path,
                )
                session.add(new_case)

        await session.commit()
        return branch_id


async def list_branches(project_id: int) -> list[dict]:
    """List all branches for a project."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Branch)
            .where(Branch.project_id == project_id)
            .order_by(desc(Branch.is_default), desc(Branch.created_at))
        )
        return [
            {
                'id': b.id,
                'project_id': b.project_id,
                'name': b.name,
                'source_branch_id': b.source_branch_id,
                'is_default': b.is_default,
                'is_empty': b.is_empty,
                'source_path': b.source_path,
                'test_path': b.test_path,
                'created_at': dt_iso(b.created_at) if b.created_at else '',
                'updated_at': dt_iso(b.updated_at) if b.updated_at else '',
            }
            for b in result.scalars().all()
        ]


async def delete_branch(branch_id: int) -> bool:
    """Delete a branch and cascade all its scoped data."""
    async with session_ctx() as session:
        # Delete scoped data in dependency order
        await session.execute(delete(Report).where(Report.branch_id == branch_id))
        await session.execute(delete(ExecutionCase).where(ExecutionCase.branch_id == branch_id))
        await session.execute(delete(Execution).where(Execution.branch_id == branch_id))
        await session.execute(delete(TaskCase).where(TaskCase.branch_id == branch_id))
        await session.execute(delete(Task).where(Task.branch_id == branch_id))
        await session.execute(delete(TestCaseDefinition).where(TestCaseDefinition.branch_id == branch_id))
        result = await session.execute(delete(Branch).where(Branch.id == branch_id))
        await session.commit()
        return result.rowcount > 0


async def set_default_branch(branch_id: int) -> bool:
    """Set a branch as the default for its project."""
    async with session_ctx() as session:
        branch_result = await session.execute(select(Branch).where(Branch.id == branch_id))
        branch = branch_result.scalar_one_or_none()
        if branch is None:
            return False
        # Unset all defaults for the project
        await session.execute(
            update(Branch).where(Branch.project_id == branch.project_id).values(is_default=False)
        )
        branch.is_default = True
        await session.commit()
        return True


async def get_default_branch(project_id: int) -> dict | None:
    """Get the default branch for a project."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Branch).where(Branch.project_id == project_id, Branch.is_default == True)
        )
        b = result.scalar_one_or_none()
        if b is None:
            return None
        return {
            'id': b.id,
            'name': b.name,
        }


async def ensure_main_branch(project_id: int, source_path: str = '', test_path: str = '') -> int:
    """Ensure a project has a 'main' default branch. Creates one if missing. Returns branch_id."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Branch).where(Branch.project_id == project_id).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing.id

        branch = Branch(
            project_id=project_id,
            name='main',
            source_branch_id=None,
            is_default=True,
            is_empty=True,
            source_path=source_path,
            test_path=test_path,
        )
        session.add(branch)
        await session.commit()
        return branch.id


# ── Test History (from ExecutionCase) ──


async def resolve_branch_id(project_id: int, version: int | None = None) -> int:
    """Resolve the effective branch_id.
    - If version is explicitly set and > 0, use that as branch_id.
    - If version is 0 or None, return 0 (meaning: no branch filter).
    """
    if version:
        return version
    return 0


async def get_latest_status_for_uids(uids: list[str]) -> dict[str, dict]:
    """Get latest execution status for multiple test case uids from ExecutionCase."""
    if not uids:
        return {}
    from sqlalchemy import func
    async with session_ctx() as session:
        # Subquery: latest end_time per uid
        subq = (
            select(
                ExecutionCase.uid,
                func.max(ExecutionCase.end_time).label('max_end_time')
            )
            .where(ExecutionCase.uid.in_(uids), ExecutionCase.end_time.isnot(None))
            .group_by(ExecutionCase.uid)
            .subquery()
        )
        result = await session.execute(
            select(ExecutionCase)
            .join(subq, (ExecutionCase.uid == subq.c.uid) & (ExecutionCase.end_time == subq.c.max_end_time))
        )
        records = result.scalars().all()
        return {
            r.uid: {
                'uid': r.uid,
                'status': r.status,
                'duration_ms': r.duration_ms,
                'executed_at': dt_iso(r.end_time) if r.end_time else '',
                'run_id': r.execution_id,
            }
            for r in records
        }


async def get_test_history(uid: str, limit: int = 5) -> list[dict]:
    """Get recent execution history for a test case from ExecutionCase."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ExecutionCase)
            .where(ExecutionCase.uid == uid, ExecutionCase.end_time.isnot(None))
            .order_by(desc(ExecutionCase.end_time))
            .limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                'uid': r.uid,
                'status': r.status,
                'duration_ms': r.duration_ms,
                'message': r.message,
                'executed_at': dt_iso(r.end_time) if r.end_time else '',
                'run_id': r.execution_id,
            }
            for r in records
        ]


async def get_test_history_for_uids(uids: list[str], limit: int = 1) -> dict[str, list[dict]]:
    """Get execution history for multiple uids from ExecutionCase."""
    if not uids:
        return {}
    async with session_ctx() as session:
        result = await session.execute(
            select(ExecutionCase)
            .where(ExecutionCase.uid.in_(uids), ExecutionCase.end_time.isnot(None))
            .order_by(desc(ExecutionCase.end_time))
        )
        records = result.scalars().all()
        history_map: dict[str, list[dict]] = {}
        for r in records:
            if r.uid not in history_map:
                history_map[r.uid] = []
            if len(history_map[r.uid]) < limit:
                history_map[r.uid].append({
                    'uid': r.uid,
                    'status': r.status,
                    'duration_ms': r.duration_ms,
                    'message': r.message,
                    'executed_at': dt_iso(r.end_time) if r.end_time else '',
                    'run_id': r.execution_id,
                })
        return history_map


# ── Task CRUD ──


async def create_task(name: str, uids: list[str], project_id: int = 0, branch_id: int = 0) -> int:
    """Create a Task and associated TaskCases. Returns task_id."""
    async with session_ctx() as session:
        task = Task(name=name, project_id=project_id, branch_id=branch_id)
        session.add(task)
        await session.flush()
        task_id = task.id
        for idx, uid in enumerate(uids):
            session.add(TaskCase(task_id=task_id, uid=uid, branch_id=branch_id, sort=idx))
        await session.commit()
        return task_id


async def get_task(task_id: int) -> dict | None:
    """Get task detail with uids."""
    async with session_ctx() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return None
        cases_result = await session.execute(
            select(TaskCase).where(TaskCase.task_id == task_id).order_by(TaskCase.sort)
        )
        uids = [c.uid for c in cases_result.scalars().all()]
        return {
            'id': task.id, 'name': task.name,
            'project_id': task.project_id,
            'status': task.status,
            'total': len(uids),
            'uids': uids,
            'create_time': dt_iso(task.create_time) if task.create_time else '',
        }


async def get_all_tasks(limit: int = 20, project_id: int | None = None, branch_id: int = 0) -> list[dict]:
    """List tasks, optionally filtered by project and branch."""
    async with session_ctx() as session:
        query = select(Task).order_by(desc(Task.create_time)).limit(limit)
        
        if project_id:
            query = query.where(Task.project_id == project_id)
        if branch_id:
            query = query.where(Task.branch_id == branch_id)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        output = []
        for t in tasks:
            count_result = await session.execute(
                select(TaskCase).where(TaskCase.task_id == t.id)
            )
            total = len(count_result.scalars().all())
            output.append({
                'id': t.id, 'name': t.name,
                'project_id': t.project_id,
                'status': t.status,
                'total': total,
                'create_time': dt_iso(t.create_time) if t.create_time else '',
            })
        return output


async def update_task_name(task_id: int, name: str) -> bool:
    """Rename a task."""
    async with session_ctx() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return False
        task.name = name
        await session.commit()
        return True


async def delete_task(task_id: int) -> bool:
    """Delete a task and its task_cases. Does NOT delete executions."""
    async with session_ctx() as session:
        await session.execute(delete(TaskCase).where(TaskCase.task_id == task_id))
        result = await session.execute(delete(Task).where(Task.id == task_id))
        await session.commit()
        return result.rowcount > 0


# ── New Execution CRUD ──


async def create_execution(task_id: int, concurrency: int = 2, sequential: bool = False, batch_size: int = 50, branch_id: int = 0) -> str:
    """Create an Execution + all ExecutionCase records. Returns execution_id."""
    from uuid import uuid4
    execution_id = uuid4().hex[:12]

    async with session_ctx() as session:
        task_result = await session.execute(select(Task).where(Task.id == task_id))
        task = task_result.scalar_one_or_none()
        if task is None:
            raise ValueError(f'Task {task_id} not found')

        cases_result = await session.execute(
            select(TaskCase).where(TaskCase.task_id == task_id).order_by(TaskCase.sort)
        )
        all_cases = cases_result.scalars().all()
        total = len(all_cases)

        exec_rec = Execution(
            execution_id=execution_id,
            task_id=task_id,
            project_id=task.project_id or 0,
            branch_id=branch_id or task.branch_id or 0,
            task_name=task.name,
            status='waiting',
            total_count=total,
            waiting_count=total,
            concurrency=concurrency,
            sequential=sequential,
        )
        session.add(exec_rec)

        for c in all_cases:
            case_def = await session.execute(
                select(TestCaseDefinition).where(
                    TestCaseDefinition.uid == c.uid,
                    TestCaseDefinition.project_id == task.project_id,
                    TestCaseDefinition.branch_id == (branch_id or task.branch_id or 0),
                )
            )
            case_def = case_def.scalar_one_or_none()
            case_name = case_def.name if case_def else c.uid
            description = case_def.description if case_def else ''
            method_name = case_def.method_name if case_def else ''
            class_name = case_def.class_name if case_def else ''
            module = case_def.module if case_def else ''

            session.add(ExecutionCase(
                execution_id=execution_id,
                uid=c.uid,
                case_name=case_name,
                description=description,
                method_name=method_name,
                class_name=class_name,
                module=module,
                status='waiting',
            ))

        await session.commit()

        return execution_id


async def create_execution_cases_batch(execution_id: str, uids: list[str], batch_size: int = 50) -> int:
    """Create next batch of ExecutionCase records for an execution. Returns count created."""
    batch_uids = uids[:batch_size]
    if not batch_uids:
        return 0
    async with session_ctx() as session:
        # Get branch_id and project_id from the execution
        exec_result = await session.execute(
            select(Execution.branch_id, Execution.project_id).where(Execution.execution_id == execution_id)
        )
        exec_row = exec_result.one_or_none()
        branch_id = exec_row.branch_id if exec_row else 0
        project_id = exec_row.project_id if exec_row else 0

        for uid in batch_uids:
            case_def = await session.execute(
                select(TestCaseDefinition).where(
                    TestCaseDefinition.uid == uid,
                    TestCaseDefinition.project_id == project_id,
                    TestCaseDefinition.branch_id == branch_id,
                )
            )
            case_def = case_def.scalar_one_or_none()
            case_name = case_def.name if case_def else uid
            description = case_def.description if case_def else ''
            method_name = case_def.method_name if case_def else ''
            class_name = case_def.class_name if case_def else ''
            module = case_def.module if case_def else ''

            session.add(ExecutionCase(
                execution_id=execution_id,
                uid=uid,
                branch_id=branch_id,
                case_name=case_name,
                description=description,
                method_name=method_name,
                class_name=class_name,
                module=module,
                status='waiting',
            ))
        await session.commit()
        return len(batch_uids)


async def get_remaining_task_case_uids(task_id: int, offset: int) -> list[str]:
    """Get TaskCase UIDs starting from offset."""
    async with session_ctx() as session:
        result = await session.execute(
            select(TaskCase.uid).where(TaskCase.task_id == task_id)
            .order_by(TaskCase.sort).offset(offset)
        )
        return [row[0] for row in result.fetchall()]


async def get_execution(execution_id: str) -> dict | None:
    """Get execution summary with counts."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Execution).where(Execution.execution_id == execution_id)
        )
        e = result.scalar_one_or_none()
        if e is None:
            return None
        return {
            'execution_id': e.execution_id,
            'task_id': e.task_id,
            'project_id': e.project_id,
            'task_name': e.task_name,
            'status': e.status,
            'total': e.total_count,
            'waiting': e.waiting_count,
            'running': e.running_count,
            'success': e.success_count,
            'fail': e.fail_count,
            'skip': e.skip_count,
            'concurrency': e.concurrency,
            'start_time': dt_iso(e.start_time) if e.start_time else '',
            'end_time': dt_iso(e.end_time) if e.end_time else '',
        }


async def get_all_executions(limit: int = 20, project_id: int | None = None, branch_id: int = 0) -> list[dict]:
    """List recent executions, optionally filtered by project and branch."""
    async with session_ctx() as session:
        query = select(Execution).order_by(desc(Execution.id)).limit(limit)
        
        if project_id:
            query = query.where(Execution.project_id == project_id)
        if branch_id:
            query = query.where(Execution.branch_id == branch_id)
        
        result = await session.execute(query)
        records = result.scalars().all()
        return [
            {
                'execution_id': e.execution_id,
                'task_id': e.task_id,
                'project_id': e.project_id,
                'task_name': e.task_name,
                'status': e.status,
                'total': e.total_count,
                'waiting': e.waiting_count,
                'running': e.running_count,
                'success': e.success_count,
                'fail': e.fail_count,
                'skip': e.skip_count,
                'concurrency': e.concurrency,
                'start_time': dt_iso(e.start_time) if e.start_time else '',
                'end_time': dt_iso(e.end_time) if e.end_time else '',
            }
            for e in records
        ]


async def get_recent_executions(project_id: int, limit: int = 2) -> list[dict]:
    """Get recent executions for a project."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Execution)
            .where(Execution.project_id == project_id)
            .order_by(desc(Execution.id))
            .limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                'execution_id': e.execution_id,
                'task_id': e.task_id,
                'task_name': e.task_name,
                'status': e.status,
                'total': e.total_count,
                'success': e.success_count,
                'fail': e.fail_count,
                'skip': e.skip_count,
                'start_time': dt_iso(e.start_time) if e.start_time else '',
                'end_time': dt_iso(e.end_time) if e.end_time else '',
                'duration': duration_between(e.start_time, e.end_time),
                'created_at': dt_iso(e.start_time) if e.start_time else '',
            }
            for e in records
        ]


async def get_executions_for_task(task_id: int) -> list[dict]:
    """Get all executions for a specific task."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Execution).where(Execution.task_id == task_id).order_by(desc(Execution.id))
        )
        records = result.scalars().all()
        return [
            {
                'execution_id': e.execution_id,
                'task_id': e.task_id, 'task_name': e.task_name,
                'status': e.status, 'total': e.total_count,
                'waiting': e.waiting_count, 'running': e.running_count,
                'success': e.success_count, 'fail': e.fail_count, 'skip': e.skip_count,
                'concurrency': e.concurrency,
                'start_time': dt_iso(e.start_time) if e.start_time else '',
                'end_time': dt_iso(e.end_time) if e.end_time else '',
            }
            for e in records
        ]


async def update_execution_status(execution_id: str, status: str) -> None:
    """Update execution status."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Execution).where(Execution.execution_id == execution_id)
        )
        e = result.scalar_one_or_none()
        if e is None:
            return
        e.status = status
        if status == 'running' and e.start_time is None:
            e.start_time = datetime.utcnow()
        if status in ('finished', 'stopped', 'failed'):
            e.end_time = datetime.utcnow()
        await session.commit()


async def update_execution_counts(execution_id: str, *, total: int | None = None,
                                   waiting: int | None = None, running: int | None = None,
                                   success: int | None = None, fail: int | None = None,
                                   skip: int | None = None) -> None:
    """Batch update execution count fields."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Execution).where(Execution.execution_id == execution_id)
        )
        e = result.scalar_one_or_none()
        if e is None:
            return
        if total is not None:
            e.total_count = total
        if waiting is not None:
            e.waiting_count = waiting
        if running is not None:
            e.running_count = running
        if success is not None:
            e.success_count = success
        if fail is not None:
            e.fail_count = fail
        if skip is not None:
            e.skip_count = skip
        await session.commit()


async def update_execution_case(execution_id: str, uid: str, status: str | None = None,
                                 duration_ms: int = 0, message: str | None = None,
                                 trace: str | None = None, logs: str | None = None,
                                 test_type: str | None = None, steps: str | None = None,
                                 screenshots: str | None = None) -> None:
    """Update a single execution_case record."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ExecutionCase).where(
                ExecutionCase.execution_id == execution_id,
                ExecutionCase.uid == uid,
            )
        )
        ec = result.scalar_one_or_none()
        if ec is None:
            return
        if status is not None:
            ec.status = status
        if duration_ms:
            ec.duration_ms = duration_ms
        if message:
            ec.message = message
        if trace:
            ec.trace = trace
        if logs:
            ec.logs = logs
        if test_type is not None:
            ec.test_type = test_type
        if steps is not None:
            ec.steps = steps
        if screenshots is not None:
            ec.screenshots = screenshots
        if status == 'running' and ec.start_time is None:
            ec.start_time = datetime.utcnow()
        if status in ('passed', 'failed', 'skipped', 'broken', 'pass', 'fail', 'skip'):
            ec.end_time = datetime.utcnow()
        await session.commit()


async def get_execution_cases(execution_id: str, page: int = 1, size: int = 50) -> dict:
    """Paginated query of execution_case records."""
    from sqlalchemy import func
    async with session_ctx() as session:
        count_result = await session.execute(
            select(func.count(ExecutionCase.id)).where(ExecutionCase.execution_id == execution_id)
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        status_order = case(
            (ExecutionCase.status == 'pass', 1),
            (ExecutionCase.status == 'fail', 2),
            (ExecutionCase.status == 'broken', 3),
            (ExecutionCase.status == 'skip', 4),
            (ExecutionCase.status == 'waiting', 5),
            (ExecutionCase.status == 'running', 6),
            else_=7,
        )
        result = await session.execute(
            select(ExecutionCase)
            .where(ExecutionCase.execution_id == execution_id)
            .order_by(status_order, ExecutionCase.id)
            .offset(offset)
            .limit(size)
        )
        records = result.scalars().all()
        items = [
            {
                'id': r.id, 'uid': r.uid,
                'case_name': r.case_name,
                'description': r.description or '',
                'method_name': r.method_name,
                'class_name': r.class_name,
                'status': r.status,
                'duration_ms': r.duration_ms,
                'start_time': dt_iso(r.start_time) if r.start_time else '',
                'end_time': dt_iso(r.end_time) if r.end_time else '',
            }
            for r in records
        ]
        return {'total': total, 'page': page, 'size': size, 'items': items}


async def get_execution_case_statistics(execution_id: str) -> dict:
    """Get execution case statistics grouped by status."""
    from sqlalchemy import func
    async with session_ctx() as session:
        result = await session.execute(
            select(ExecutionCase.status, func.count(ExecutionCase.id))
            .where(ExecutionCase.execution_id == execution_id)
            .group_by(ExecutionCase.status)
        )
        counts = {r[0]: r[1] for r in result.all()}
        total = sum(counts.values())
        return {
            'total': total,
            'pass': counts.get('pass', 0),
            'fail': counts.get('fail', 0),
            'broken': counts.get('broken', 0),
            'skip': counts.get('skip', 0),
            'running': counts.get('running', 0),
            'waiting': counts.get('waiting', 0),
        }


async def get_execution_case_log(execution_case_id: int) -> dict | None:
    """Get log details for a single execution case."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ExecutionCase).where(ExecutionCase.id == execution_case_id)
        )
        r = result.scalar_one_or_none()
        if r is None:
            return None
        return {
            'id': r.id, 'uid': r.uid, 'case_name': r.case_name,
            'status': r.status, 'duration_ms': r.duration_ms,
            'message': r.message, 'trace': r.trace, 'logs': r.logs,
            'steps': r.steps or '',
            'screenshots': r.screenshots or '',
            'start_time': dt_iso(r.start_time) if r.start_time else '',
            'end_time': dt_iso(r.end_time) if r.end_time else '',
        }


async def get_all_execution_case_uids(execution_id: str) -> list[dict]:
    """Get all uids with class/method names for executor."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ExecutionCase.uid, ExecutionCase.class_name, ExecutionCase.method_name)
            .where(ExecutionCase.execution_id == execution_id)
            .order_by(ExecutionCase.id)
        )
        return [{'uid': r[0], 'class_name': r[1], 'method_name': r[2]} for r in result.all()]


async def get_execution_cases_full(execution_id: str) -> list[dict]:
    """Return full ExecutionCase records for an execution (for history/report)."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ExecutionCase)
            .where(ExecutionCase.execution_id == execution_id)
            .order_by(ExecutionCase.id)
        )
        records = result.scalars().all()
        return [
            {
                'uid': r.uid,
                'case_name': r.case_name,
                'description': r.description or '',
                'method_name': r.method_name,
                'class_name': r.class_name,
                'module': r.module,
                'status': r.status,
                'duration_ms': r.duration_ms,
                'message': r.message,
                'trace': r.trace,
                'logs': r.logs,
                'test_type': r.test_type,
                'steps': r.steps,
                'screenshots': r.screenshots,
            }
            for r in records
        ]


async def bulk_fail_pending_cases(execution_id: str) -> int:
    """Mark all waiting/running execution_cases as broken. Returns count updated."""
    from sqlalchemy import update
    async with session_ctx() as session:
        result = await session.execute(
            update(ExecutionCase)
            .where(
                ExecutionCase.execution_id == execution_id,
                ExecutionCase.status.in_(['waiting', 'running']),
            )
            .values(status='broken', end_time=datetime.utcnow())
        )
        await session.commit()
        return result.rowcount

async def bulk_update_broken_cases_logs(execution_id: str, logs_text: str) -> int:
    """Update message for all broken execution_cases in an execution."""
    from sqlalchemy import update
    async with session_ctx() as session:
        result = await session.execute(
            update(ExecutionCase)
            .where(
                ExecutionCase.execution_id == execution_id,
                ExecutionCase.status == 'broken',
            )
            .values(message=logs_text[:5000])
        )
        await session.commit()
        return result.rowcount


async def mark_cases_as_running(execution_id: str, count: int) -> list[dict]:
    """Mark the first `count` waiting execution_cases as running. Returns list of updated cases."""
    from sqlalchemy import update
    async with session_ctx() as session:
        # Get the first `count` waiting cases
        result = await session.execute(
            select(ExecutionCase)
            .where(
                ExecutionCase.execution_id == execution_id,
                ExecutionCase.status == 'waiting',
            )
            .order_by(ExecutionCase.id)
            .limit(count)
        )
        cases = result.scalars().all()
        if not cases:
            return []
        ids = [c.id for c in cases]
        await session.execute(
            update(ExecutionCase)
            .where(ExecutionCase.id.in_(ids))
            .values(status='running', start_time=datetime.utcnow())
        )
        await session.commit()
        return [
            {'uid': c.uid, 'case_name': c.case_name, 'method_name': c.method_name,
             'class_name': c.class_name, 'id': c.id}
            for c in cases
        ]


# ── Discovery Cache Persistence ──

async def replace_discovery_cache(test_cases: list[dict], project_id: int = 0, branch_id: int = 0) -> set[str]:
    """Replace all test case definitions in DB with a fresh set from discovery.
    Returns the set of UIDs that are new (didn't exist in previous sync)."""
    async with session_ctx() as session:
        # Load existing UIDs for this project+branch before deletion
        existing_result = await session.execute(
            select(TestCaseDefinition.uid).where(
                TestCaseDefinition.project_id == project_id,
                TestCaseDefinition.branch_id == branch_id,
            )
        )
        existing_uids: set[str] = {row[0] for row in existing_result.fetchall()}

        await session.execute(
            delete(TestCaseDefinition).where(
                TestCaseDefinition.project_id == project_id,
                TestCaseDefinition.branch_id == branch_id,
            )
        )
        await session.flush()  # Ensure DELETE is executed before INSERTs
        now = datetime.utcnow()
        seen: set[str] = set()
        new_uids: set[str] = set()
        for c in test_cases:
            uid = c['uid']
            if uid in seen:
                continue
            seen.add(uid)
            if uid not in existing_uids:
                new_uids.add(uid)
            record = TestCaseDefinition(
                uid=uid,
                project_id=project_id,
                branch_id=branch_id,
                name=c.get('name', ''),
                method_name=c.get('methodName', c.get('method_name', '')),
                class_name=c.get('className', c.get('class_name', '')),
                module=c.get('module', ''),
                full_name=c.get('fullName', c.get('full_name', '')),
                description=c.get('description', ''),
                steps=c.get('steps', ''),
                tags=','.join(c.get('tags', [])) if isinstance(c.get('tags'), list) else c.get('tags', ''),
                test_type=c.get('testType', c.get('test_type', 'api')),
                file_path=c.get('filePath', c.get('file_path', '')),
                is_new=(uid in new_uids),
                updated_at=now,
            )
            session.add(record)
        await session.commit()
        return new_uids


async def load_discovery_cache(project_id: int = 0, branch_id: int = 0) -> tuple[list[dict], int]:
    """Load all test case definitions from DB, optionally filtered by project_id and branch_id.
    When branch_id is 0 (unspecified), don't filter by branch — show all data."""
    async with session_ctx() as session:
        query = select(TestCaseDefinition)
        if project_id:
            query = query.where(TestCaseDefinition.project_id == project_id)
        if branch_id:
            query = query.where(TestCaseDefinition.branch_id == branch_id)
        result = await session.execute(query)
        records = result.scalars().all()
        test_cases = [
            {
                'uid': r.uid,
                'name': r.name,
                'methodName': r.method_name,
                'className': r.class_name,
                'module': r.module,
                'fullName': r.full_name,
                'description': r.description,
                'steps': r.steps,
                'tags': [t for t in r.tags.split(',') if t] if r.tags else [],
                'isNew': r.is_new,
                'testType': r.test_type,
                'filePath': r.file_path,
            }
            for r in records
        ]
        return test_cases, len(test_cases)


async def get_discovery_count() -> int:
    """Return total number of stored test case definitions."""
    async with session_ctx() as session:
        result = await session.execute(select(TestCaseDefinition))
        return len(result.scalars().all())


async def get_test_case_by_uid(uid: str, project_id: int = 0, branch_id: int = 0) -> dict | None:
    """Look up a single test case by uid + project + branch from the database."""
    async with session_ctx() as session:
        result = await session.execute(
            select(TestCaseDefinition).where(
                TestCaseDefinition.uid == uid,
                TestCaseDefinition.project_id == project_id,
                TestCaseDefinition.branch_id == branch_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return {
            'uid': record.uid,
            'name': record.name,
            'methodName': record.method_name,
            'className': record.class_name,
            'module': record.module,
            'fullName': record.full_name,
            'description': record.description,
            'steps': record.steps,
            'tags': [t for t in record.tags.split(',') if t] if record.tags else [],
            'status': 'unknown',
            'isNew': record.is_new,
            'testType': record.test_type,
            'filePath': record.file_path,
        }


async def update_test_case(
    uid: str,
    project_id: int,
    branch_id: int,
    description: str | None = None,
    steps: str | None = None,
    module: str | None = None,
) -> dict | None:
    """Update editable fields of a single test case (description/steps/module)."""
    async with session_ctx() as session:
        result = await session.execute(
            select(TestCaseDefinition).where(
                TestCaseDefinition.uid == uid,
                TestCaseDefinition.project_id == project_id,
                TestCaseDefinition.branch_id == branch_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        if description is not None:
            record.description = description
        if steps is not None:
            record.steps = steps
        if module is not None:
            record.module = module
        record.updated_at = datetime.utcnow()
        await session.commit()
        # Re-read to return fresh dict
        fresh = await session.execute(
            select(TestCaseDefinition).where(
                TestCaseDefinition.uid == uid,
                TestCaseDefinition.project_id == project_id,
                TestCaseDefinition.branch_id == branch_id,
            )
        )
        rec = fresh.scalar_one_or_none()
        if rec is None:
            return None
        return {
            'uid': rec.uid,
            'name': rec.name,
            'methodName': rec.method_name,
            'className': rec.class_name,
            'module': rec.module,
            'fullName': rec.full_name,
            'description': rec.description,
            'steps': rec.steps,
            'tags': [t for t in rec.tags.split(',') if t] if rec.tags else [],
            'status': 'unknown',
            'isNew': rec.is_new,
            'testType': rec.test_type,
            'filePath': rec.file_path,
        }


async def load_discovery_raw() -> list[dict]:
    """Load all discovery records as flat dicts (for uid mapping in executor)."""
    async with session_ctx() as session:
        result = await session.execute(select(TestCaseDefinition))
        records = result.scalars().all()
        return [
            {
                'uid': r.uid,
                'fullName': r.full_name,
                'testType': r.test_type,
                'filePath': r.file_path,
            }
            for r in records
        ]


# ── Paginated Case Query ──


async def get_cases_by_project_paginated(
    project_id: int,
    page: int = 1,
    size: int = 50,
    search: str = '',
    test_type: str = '',
    status: str = '',
    module: str = '',
) -> dict:
    """Get paginated test cases for a project with server-side filtering."""
    from sqlalchemy import func, or_
    async with session_ctx() as session:
        query = select(TestCaseDefinition).where(TestCaseDefinition.project_id == project_id)

        if search:
            pattern = f'%{search}%'
            query = query.where(
                or_(
                    TestCaseDefinition.full_name.like(pattern),
                    TestCaseDefinition.method_name.like(pattern),
                    TestCaseDefinition.description.like(pattern),
                )
            )
        if test_type:
            query = query.where(TestCaseDefinition.test_type == test_type)
        if module:
            query = query.where(TestCaseDefinition.module == module)

        count_q = select(func.count(TestCaseDefinition.uid)).where(TestCaseDefinition.project_id == project_id)
        if search:
            pattern = f'%{search}%'
            count_q = count_q.where(
                or_(
                    TestCaseDefinition.full_name.like(pattern),
                    TestCaseDefinition.method_name.like(pattern),
                    TestCaseDefinition.description.like(pattern),
                )
            )
        if test_type:
            count_q = count_q.where(TestCaseDefinition.test_type == test_type)
        if module:
            count_q = count_q.where(TestCaseDefinition.module == module)

        total = (await session.execute(count_q)).scalar() or 0

        offset = (page - 1) * size
        query = query.order_by(TestCaseDefinition.module, TestCaseDefinition.class_name, TestCaseDefinition.method_name)
        query = query.offset(offset).limit(size)
        result = await session.execute(query)
        records = result.scalars().all()

        items = []
        uids = [r.uid for r in records]
        if uids:
            latest_status = await get_latest_status_for_uids(uids)
        else:
            latest_status = {}

        for r in records:
            ls = latest_status.get(r.uid, {})
            items.append({
                'uid': r.uid,
                'name': r.name,
                'methodName': r.method_name,
                'className': r.class_name,
                'module': r.module,
                'fullName': r.full_name,
                'description': r.description,
                'tags': [t for t in r.tags.split(',') if t] if r.tags else [],
                'testType': r.test_type,
                'filePath': r.file_path,
                'isNew': r.is_new,
                'status': ls.get('status', 'unknown'),
                'duration_ms': ls.get('duration_ms', 0),
            })

        return {
            'items': items,
            'total': total,
            'page': page,
            'size': size,
            'pages': max(1, (total + size - 1) // size),
        }


async def get_case_module_stats(project_id: int) -> dict:
    """Get module metadata for a project (module tree + counts)."""
    from sqlalchemy import func
    async with session_ctx() as session:
        result = await session.execute(
            select(TestCaseDefinition.module, func.count(TestCaseDefinition.uid))
            .where(TestCaseDefinition.project_id == project_id)
            .group_by(TestCaseDefinition.module)
            .order_by(TestCaseDefinition.module)
        )
        module_rows = result.fetchall()

        modules = []
        total_active = 0
        total_new = 0
        for mod_name, count in module_rows:
            modules.append({
                'name': mod_name,
                'case_count': count,
            })
            total_active += count

        new_result = await session.execute(
            select(func.count(TestCaseDefinition.uid))
            .where(TestCaseDefinition.project_id == project_id, TestCaseDefinition.is_new == True)
        )
        total_new = new_result.scalar() or 0

        return {
            'modules': modules,
            'total_active': total_active,
            'total_new': total_new,
        }


# ── Project CRUD ──


async def create_project(name: str, source_type: str, server_path: str = '',
                         test_path: str = '', report_output: str = '',
                         creator_id: int = 0) -> int:
    """Create a new Project. Returns project_id."""
    async with session_ctx() as session:
        project = Project(
            name=name,
            source_type=source_type,
            server_path=server_path,
            test_path=test_path,
            report_output=report_output,
            creator_id=creator_id,
        )
        session.add(project)
        await session.flush()
        project_id = project.id
        # Auto-add creator as project member
        if creator_id:
            session.add(ProjectMember(project_id=project_id, user_id=creator_id))
        await session.commit()
        return project_id


async def get_project(project_id: int) -> dict | None:
    """Get project detail."""
    async with session_ctx() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            return None
        # Get creator name
        creator_name = ''
        if project.creator_id:
            creator_result = await session.execute(select(User).where(User.id == project.creator_id))
            creator = creator_result.scalar_one_or_none()
            if creator:
                creator_name = creator.nickname or creator.username
        # Get member count
        member_count_result = await session.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
        )
        member_count = len(member_count_result.scalars().all())
        return {
            'id': project.id,
            'name': project.name,
            'source_type': project.source_type,
            'server_path': project.server_path,
            'test_path': project.test_path,
            'report_output': project.report_output,
            'is_active': project.is_active,
            'case_count': project.case_count,
            'new_case_count': project.new_case_count,
            'creator_id': project.creator_id,
            'creator_name': creator_name,
            'member_count': member_count,
            'last_synced_at': dt_iso(project.last_synced_at) if project.last_synced_at else '',
            'created_at': dt_iso(project.created_at) if project.created_at else '',
        }


async def get_all_projects(user_id: int | None = None) -> list[dict]:
    """List all projects.

    If user_id is provided and is not admin (id=1), filter to only show
    projects where the user is the creator or a member.
    """
    active_id = None
    if user_id is not None:
        active_id = await _resolve_user_active_project_id(user_id)
    async with session_ctx() as session:
        query = select(Project).order_by(desc(Project.created_at))

        # Filter by user membership (non-admin users)
        if user_id is not None and user_id != 1:
            # Get project_ids where user is a member
            member_result = await session.execute(
                select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
            )
            member_project_ids = {row[0] for row in member_result.fetchall()}
            # Also include projects where user is creator
            query = query.where(
                (Project.id.in_(member_project_ids)) | (Project.creator_id == user_id)
            )

        result = await session.execute(query)
        projects = result.scalars().all()

        output = []
        for p in projects:
            creator_name = ''
            if p.creator_id:
                creator_result = await session.execute(select(User).where(User.id == p.creator_id))
                creator = creator_result.scalar_one_or_none()
                if creator:
                    creator_name = creator.nickname or creator.username
            member_count_result = await session.execute(
                select(ProjectMember).where(ProjectMember.project_id == p.id)
            )
            member_count = len(member_count_result.scalars().all())
            output.append({
                'id': p.id,
                'name': p.name,
                'source_type': p.source_type,
                'server_path': p.server_path,
                'test_path': p.test_path,
                'report_output': p.report_output,
                'is_active': (active_id is not None and p.id == active_id)
                             if user_id is not None else p.is_active,
                'case_count': p.case_count,
                'new_case_count': p.new_case_count,
                'creator_id': p.creator_id,
                'creator_name': creator_name,
                'member_count': member_count,
                'last_synced_at': dt_iso(p.last_synced_at) if p.last_synced_at else '',
                'created_at': dt_iso(p.created_at) if p.created_at else '',
            })
        return output


async def _resolve_user_active_project_id(user_id: int) -> int | None:
    """Return the active project id for a user, auto-selecting if none is recorded.

    Auto-selection rule: the project the user joined most recently (by membership
    insertion order). Returns None if the user belongs to no project.
    """
    async with session_ctx() as session:
        row = await session.execute(
            select(UserActiveProject).where(UserActiveProject.user_id == user_id)
        )
        uap = row.scalar_one_or_none()
        if uap:
            exist = await session.execute(select(Project).where(Project.id == uap.project_id))
            if exist.scalar_one_or_none():
                return uap.project_id

        members = await session.execute(
            select(ProjectMember)
            .where(ProjectMember.user_id == user_id)
            .order_by(desc(ProjectMember.id))
        )
        latest = members.scalars().first()
        if latest is None:
            return None
        pid = latest.project_id
        if uap:
            uap.project_id = pid
            uap.updated_at = datetime.utcnow()
        else:
            session.add(UserActiveProject(user_id=user_id, project_id=pid))
        await session.commit()
        return pid


async def get_active_project(user_id: int | None = None) -> dict | None:
    """Get the active project for a user (per-user), auto-selecting if needed."""
    project_id = None
    if user_id is not None:
        project_id = await _resolve_user_active_project_id(user_id)
    async with session_ctx() as session:
        if project_id is None and user_id is None:
            # Global fallback (legacy) — used by internal services without a user
            result = await session.execute(select(Project).where(Project.is_active == True))
            project = result.scalar_one_or_none()
            if project is not None:
                project_id = project.id
        if project_id is None:
            return None
        project = (
            await session.execute(select(Project).where(Project.id == project_id))
        ).scalar_one_or_none()
        if project is None:
            return None
        creator_name = ''
        if project.creator_id:
            creator_result = await session.execute(select(User).where(User.id == project.creator_id))
            creator = creator_result.scalar_one_or_none()
            if creator:
                creator_name = creator.nickname or creator.username
        member_count_result = await session.execute(
            select(ProjectMember).where(ProjectMember.project_id == project.id)
        )
        member_count = len(member_count_result.scalars().all())
        return {
            'id': project.id,
            'name': project.name,
            'source_type': project.source_type,
            'server_path': project.server_path,
            'test_path': project.test_path,
            'report_output': project.report_output,
            'is_active': True,
            'case_count': project.case_count,
            'new_case_count': project.new_case_count,
            'creator_id': project.creator_id,
            'creator_name': creator_name,
            'member_count': member_count,
            'last_synced_at': dt_iso(project.last_synced_at) if project.last_synced_at else '',
            'created_at': dt_iso(project.created_at) if project.created_at else '',
        }


async def set_project_active(user_id: int | None, project_id: int) -> bool:
    """Set a project as the active project for a user (per-user)."""
    async with session_ctx() as session:
        project = (
            await session.execute(select(Project).where(Project.id == project_id))
        ).scalar_one_or_none()
        if project is None:
            return False
        if user_id is None:
            # Global fallback (legacy)
            await session.execute(update(Project).values(is_active=False))
            project.is_active = True
            await session.commit()
            return True
        # Verify membership before allowing activation
        member = await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
            )
        )
        if member.scalar_one_or_none() is None:
            return False
        uap = (
            await session.execute(select(UserActiveProject).where(UserActiveProject.user_id == user_id))
        ).scalar_one_or_none()
        if uap:
            uap.project_id = project_id
            uap.updated_at = datetime.utcnow()
        else:
            session.add(UserActiveProject(user_id=user_id, project_id=project_id))
        await session.commit()
        return True


async def update_project(project_id: int, **kwargs) -> bool:
    """Update project fields."""
    from sqlalchemy import update
    async with session_ctx() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            return False
        await session.execute(
            update(Project).where(Project.id == project_id).values(**kwargs)
        )
        await session.commit()
        return True


async def delete_project(project_id: int) -> bool:
    """Delete a project and its project_cases."""
    async with session_ctx() as session:
        await session.execute(delete(ProjectCase).where(ProjectCase.project_id == project_id))
        result = await session.execute(delete(Project).where(Project.id == project_id))
        await session.commit()
        return result.rowcount > 0


async def update_project_case_count(project_id: int, case_count: int, new_case_count: int) -> None:
    """Update project case counts."""
    async with session_ctx() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            return
        project.case_count = case_count
        project.new_case_count = new_case_count
        project.last_synced_at = datetime.utcnow()
        await session.commit()


# ── ProjectCase CRUD ──


async def sync_project_cases(project_id: int, current_uids: list[str]) -> tuple[int, int]:
    """Sync project_cases with current_uids.
    
    Returns (added_count, deleted_count).
    - New uids are added with status='new'
    - Existing uids stay with their current status
    - Deleted uids are marked with status='deleted'
    """
    async with session_ctx() as session:
        existing_result = await session.execute(
            select(ProjectCase).where(ProjectCase.project_id == project_id)
        )
        existing_records = existing_result.scalars().all()
        existing_uids = {r.uid: r for r in existing_records}

        current_set = set(current_uids)
        existing_set = set(existing_uids.keys())

        added = 0
        deleted = 0

        for uid in current_set - existing_set:
            session.add(ProjectCase(project_id=project_id, uid=uid, status='new'))
            added += 1

        for uid in existing_set - current_set:
            record = existing_uids[uid]
            if record.status != 'deleted':
                record.status = 'deleted'
                deleted += 1

        await session.commit()
        return added, deleted


async def confirm_project_case(project_id: int, uid: str) -> bool:
    """Confirm a new case (status -> active)."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ProjectCase).where(
                ProjectCase.project_id == project_id,
                ProjectCase.uid == uid,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return False
        record.status = 'active'
        await session.commit()
        return True


async def confirm_all_project_cases(project_id: int) -> int:
    """Confirm all new cases for a project. Returns count updated."""
    from sqlalchemy import update
    async with session_ctx() as session:
        result = await session.execute(
            update(ProjectCase)
            .where(ProjectCase.project_id == project_id, ProjectCase.status == 'new')
            .values(status='active')
        )
        await session.commit()
        return result.rowcount


async def get_project_case_status(project_id: int, uid: str) -> str | None:
    """Get the status of a case in a project."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ProjectCase).where(
                ProjectCase.project_id == project_id,
                ProjectCase.uid == uid,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return record.status


async def get_project_new_case_count(project_id: int) -> int:
    """Get count of new cases for a project."""
    from sqlalchemy import func
    async with session_ctx() as session:
        result = await session.execute(
            select(func.count(ProjectCase.id))
            .where(ProjectCase.project_id == project_id, ProjectCase.status == 'new')
        )
        return result.scalar() or 0


async def get_project_case_uids(project_id: int, status: str | None = None) -> list[str]:
    """Get all case uids for a project, optionally filtered by status."""
    async with session_ctx() as session:
        query = select(ProjectCase.uid).where(ProjectCase.project_id == project_id)
        if status is not None:
            query = query.where(ProjectCase.status == status)
        result = await session.execute(query)
        return [row[0] for row in result.fetchall()]


async def get_project_case_count(project_id: int, branch_id: int = 0) -> int:
    """Get count of test cases in a specific branch."""
    from sqlalchemy import func
    async with session_ctx() as session:
        where = [TestCaseDefinition.project_id == project_id]
        if branch_id:
            where.append(TestCaseDefinition.branch_id == branch_id)
        result = await session.execute(
            select(func.count(TestCaseDefinition.uid)).where(*where)
        )
        return result.scalar() or 0


async def get_project_cases(project_id: int) -> list[dict]:
    """Get all project-level case associations for a project."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ProjectCase).where(ProjectCase.project_id == project_id)
        )
        records = result.scalars().all()
        return [
            {'case_uid': r.uid, 'status': r.status}
            for r in records
        ]


# ── Report CRUD ──


async def create_report(execution_id: str, project_id: int, summary: dict | None = None,
                        module_groups: dict | None = None, results: list | None = None) -> int:
    """Save a report to the database. Returns report id."""
    import json
    async with session_ctx() as session:
        report = Report(
            execution_id=execution_id,
            project_id=project_id,
            summary=json.dumps(summary, ensure_ascii=False) if summary else None,
            module_groups=json.dumps(module_groups, ensure_ascii=False) if module_groups else None,
            results=json.dumps(results, ensure_ascii=False) if results else None,
        )
        session.add(report)
        await session.flush()
        report_id = report.id
        await session.commit()
        return report_id


async def get_report_by_id(report_id: int) -> dict | None:
    """Get a single report by database ID."""
    import json
    async with session_ctx() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        r = result.scalar_one_or_none()
        if r is None:
            return None
        return {
            'id': r.id,
            'execution_id': r.execution_id,
            'project_id': r.project_id,
            'summary': json.loads(r.summary) if r.summary else {},
            'module_groups': json.loads(r.module_groups) if r.module_groups else {},
            'results': json.loads(r.results) if r.results else [],
            'created_at': dt_iso(r.created_at) if r.created_at else '',
        }


async def get_report_by_execution(execution_id: str) -> dict | None:
    """Get a single report by execution ID."""
    import json
    async with session_ctx() as session:
        result = await session.execute(
            select(Report).where(Report.execution_id == execution_id).order_by(desc(Report.id))
        )
        r = result.scalar_one_or_none()
        if r is None:
            return None
        return {
            'id': r.id,
            'execution_id': r.execution_id,
            'project_id': r.project_id,
            'summary': json.loads(r.summary) if r.summary else {},
            'module_groups': json.loads(r.module_groups) if r.module_groups else {},
            'results': json.loads(r.results) if r.results else [],
            'created_at': dt_iso(r.created_at) if r.created_at else '',
        }


async def get_reports_by_project(project_id: int, page: int = 1, size: int = 20, branch_id: int = 0) -> dict:
    """Get paginated reports for a project, optionally filtered by branch."""
    import json
    from sqlalchemy import func
    async with session_ctx() as session:
        count_q = select(func.count(Report.id)).where(Report.project_id == project_id)
        if branch_id:
            count_q = count_q.where(Report.branch_id == branch_id)
        total = (await session.execute(count_q)).scalar() or 0

        offset = (page - 1) * size
        query = (
            select(Report)
            .where(Report.project_id == project_id)
            .order_by(desc(Report.id))
            .offset(offset)
            .limit(size)
        )
        if branch_id:
            query = query.where(Report.branch_id == branch_id)
        result = await session.execute(query)
        records = result.scalars().all()

        items = []
        for r in records:
            summary = json.loads(r.summary) if r.summary else {}
            items.append({
                'id': r.id,
                'execution_id': r.execution_id,
                'project_id': r.project_id,
                'timestamp': summary.get('timestamp', '') or summary.get('generatedAt', ''),
                'total': summary.get('total', 0),
                'passed': summary.get('passed', 0),
                'failed': summary.get('failed', 0),
                'passRate': summary.get('passRate', 0),
                'totalDuration': summary.get('totalDuration', ''),
                'created_at': dt_iso(r.created_at) if r.created_at else '',
            })

        return {
            'items': items,
            'total': total,
            'page': page,
            'size': size,
            'pages': max(1, (total + size - 1) // size),
        }


async def delete_report(report_id: int) -> bool:
    """Delete a report by database ID."""
    async with session_ctx() as session:
        result = await session.execute(delete(Report).where(Report.id == report_id))
        await session.commit()
        return result.rowcount > 0


# ── User CRUD ──

async def create_user(username: str, nickname: str, password: str) -> int:
    """Create a new user with bcrypt-hashed password. Returns user id."""
    from passlib.hash import bcrypt
    password_hash = bcrypt.hash(password)
    async with session_ctx() as session:
        user = User(
            username=username,
            nickname=nickname,
            password_hash=password_hash,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


async def get_user_by_username(username: str) -> dict | None:
    """Get a user by username. Returns dict or None."""
    async with session_ctx() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return {
            'id': user.id,
            'username': user.username,
            'nickname': user.nickname,
            'password_hash': user.password_hash,
            'avatar_url': user.avatar_url,
            'is_active': user.is_active,
            'created_at': dt_iso(user.created_at) if user.created_at else '',
        }


async def get_user_by_id(user_id: int) -> dict | None:
    """Get a user by id. Returns dict or None."""
    async with session_ctx() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return {
            'id': user.id,
            'username': user.username,
            'nickname': user.nickname,
            'avatar_url': user.avatar_url,
            'is_active': user.is_active,
            'created_at': dt_iso(user.created_at) if user.created_at else '',
        }


async def search_users(q: str) -> list[dict]:
    """Search users by username or nickname (LIKE %q%)."""
    async with session_ctx() as session:
        pattern = f'%{q}%'
        result = await session.execute(
            select(User).where(
                User.username.like(pattern) | User.nickname.like(pattern)
            ).limit(50)
        )
        users = result.scalars().all()
        return [
            {
                'id': u.id,
                'username': u.username,
                'nickname': u.nickname,
                'avatar_url': u.avatar_url,
            }
            for u in users
        ]


async def update_password(user_id: int, new_password: str) -> bool:
    """Update user password (bcrypt-hashed). Returns True if successful."""
    from passlib.hash import bcrypt
    password_hash = bcrypt.hash(new_password)
    async with session_ctx() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.password_hash = password_hash
        await session.commit()
        return True


async def update_user_profile(user_id: int, **kwargs) -> bool:
    """Update user profile fields (nickname, avatar_url)."""
    async with session_ctx() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await session.commit()
        return True


async def update_user_avatar(user_id: int, avatar_url: str) -> bool:
    """Update user avatar URL. Returns True if successful."""
    async with session_ctx() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.avatar_url = avatar_url
        await session.commit()
        return True


async def get_users_batch(ids: list[int]) -> list[dict]:
    """Get multiple users by their IDs."""
    if not ids:
        return []
    async with session_ctx() as session:
        result = await session.execute(
            select(User).where(User.id.in_(ids))
        )
        users = result.scalars().all()
        return [
            {
                'id': u.id,
                'username': u.username,
                'nickname': u.nickname,
                'avatar_url': u.avatar_url,
            }
            for u in users
        ]


# ── Project Member CRUD ──


async def add_project_member(project_id: int, user_id: int) -> bool:
    """Add a user to a project. Returns False if already a member."""
    async with session_ctx() as session:
        existing = await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        if existing.scalar_one_or_none():
            return False
        session.add(ProjectMember(project_id=project_id, user_id=user_id))
        await session.commit()
        return True


async def remove_project_member(project_id: int, user_id: int) -> bool:
    """Remove a user from a project. Returns False if not a member."""
    async with session_ctx() as session:
        result = await session.execute(
            delete(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        await session.commit()
        return result.rowcount > 0


async def get_project_members(project_id: int) -> list[dict]:
    """Get all members of a project with user info."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.id)
        )
        members = result.scalars().all()
        output = []
        for m in members:
            user_result = await session.execute(select(User).where(User.id == m.user_id))
            user = user_result.scalar_one_or_none()
            output.append({
                'id': m.id,
                'user_id': m.user_id,
                'username': user.username if user else '',
                'nickname': user.nickname if user else '',
                'avatar_url': user.avatar_url if user else '',
                'created_at': dt_iso(m.created_at) if m.created_at else '',
            })
        return output


async def is_project_member(project_id: int, user_id: int) -> bool:
    """Check if a user is a member of a project."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None


async def get_user_projects(user_id: int) -> list[int]:
    """Get list of project_ids where the user is a member."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
        )
        return [row[0] for row in result.fetchall()]


# ── Project Note CRUD ──


async def get_project_note(project_id: int) -> dict | None:
    """Get the project note for a given project. Returns None if no note exists."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ProjectNote).where(ProjectNote.project_id == project_id)
        )
        note = result.scalar_one_or_none()
        if note is None:
            return None
        return {
            'id': note.id,
            'project_id': note.project_id,
            'content': note.content,
            'updated_by': note.updated_by,
            'created_at': dt_iso(note.created_at) if note.created_at else '',
            'updated_at': dt_iso(note.updated_at) if note.updated_at else '',
        }


async def upsert_project_note(project_id: int, content: str, updated_by: int) -> dict:
    """Create or update the project note. Returns the note dict."""
    async with session_ctx() as session:
        result = await session.execute(
            select(ProjectNote).where(ProjectNote.project_id == project_id)
        )
        note = result.scalar_one_or_none()
        if note:
            note.content = content
            note.updated_by = updated_by
        else:
            note = ProjectNote(
                project_id=project_id,
                content=content,
                updated_by=updated_by,
            )
            session.add(note)
        await session.flush()
        await session.commit()
        return {
            'id': note.id,
            'project_id': note.project_id,
            'content': note.content,
            'updated_by': note.updated_by,
            'created_at': dt_iso(note.created_at) if note.created_at else '',
            'updated_at': dt_iso(note.updated_at) if note.updated_at else '',
        }


# ── Defect Module CRUD ──


async def create_defect_module(project_id: int, data, branch_id: int = 0) -> int:
    """Create a defect module. Returns module id."""
    async with session_ctx() as session:
        module = DefectModule(
            project_id=project_id,
            branch_id=branch_id,
            name=data.name,
            parent_id=data.parent_id,
            sort_order=data.sort_order,
        )
        session.add(module)
        await session.flush()
        module_id = module.id
        await session.commit()
        return module_id


async def get_defect_modules(project_id: int, branch_id: int = 0) -> list[dict]:
    """Get defect modules for a project, optionally scoped to a branch.

    When branch_id > 0, only modules of that branch are returned. If that
    branch has no modules yet, fall back to the project-level modules
    (branch_id = 0) for backward compatibility with pre-branch data.
    """
    async with session_ctx() as session:
        query = select(DefectModule).where(DefectModule.project_id == project_id)
        if branch_id > 0:
            query = query.where(DefectModule.branch_id == branch_id)
        result = await session.execute(
            query.order_by(DefectModule.sort_order, DefectModule.id)
        )
        modules = result.scalars().all()
        if not modules and branch_id > 0:
            # Fall back to project-level (legacy) modules
            legacy = await session.execute(
                select(DefectModule)
                .where(DefectModule.project_id == project_id, DefectModule.branch_id == 0)
                .order_by(DefectModule.sort_order, DefectModule.id)
            )
            modules = legacy.scalars().all()
        return [
            {
                'id': m.id,
                'project_id': m.project_id,
                'branch_id': m.branch_id,
                'name': m.name,
                'parent_id': m.parent_id,
                'sort_order': m.sort_order,
                'created_at': dt_iso(m.created_at) if m.created_at else '',
                'updated_at': dt_iso(m.updated_at) if m.updated_at else '',
            }
            for m in modules
        ]


async def update_defect_module(module_id: int, data) -> bool:
    """Update a defect module. Returns True if updated."""
    async with session_ctx() as session:
        result = await session.execute(
            select(DefectModule).where(DefectModule.id == module_id)
        )
        module = result.scalar_one_or_none()
        if module is None:
            return False
        if data.name is not None:
            module.name = data.name
        if data.parent_id is not None:
            module.parent_id = data.parent_id
        if data.sort_order is not None:
            module.sort_order = data.sort_order
        await session.commit()
        return True


async def delete_defect_module(module_id: int) -> bool:
    """Delete a defect module. Returns True if deleted."""
    async with session_ctx() as session:
        module_result = await session.execute(
            select(DefectModule).where(DefectModule.id == module_id)
        )
        module = module_result.scalar_one_or_none()
        if module is None:
            return False
        parent_id = module.parent_id
        # Reassign children to the parent of the deleted module
        await session.execute(
            update(DefectModule)
            .where(DefectModule.parent_id == module_id)
            .values(parent_id=parent_id)
        )
        # Clear module_id reference in defects
        await session.execute(
            update(Defect)
            .where(Defect.module_id == module_id)
            .values(module_id=0)
        )
        result = await session.execute(
            delete(DefectModule).where(DefectModule.id == module_id)
        )
        await session.commit()
        return result.rowcount > 0


# ── Defect CRUD ──


async def _resolve_case_name(project_id: int, branch_id: int, case_uid: str) -> str:
    """Resolve a test case's display name (description) for a defect link."""
    if not case_uid:
        return ''
    try:
        async with session_ctx() as session:
            stmt = select(TestCaseDefinition).where(
                TestCaseDefinition.uid == case_uid,
                TestCaseDefinition.project_id == project_id,
            )
            # Prefer the exact branch; fall back to any branch since a case's
            # cached branch (discovery) may differ from the defect's branch.
            stmt = stmt.order_by(
                (TestCaseDefinition.branch_id == branch_id).desc()  # exact match first
            )
            rec = (await session.execute(stmt)).scalars().first()
            return (rec.description or rec.name or '') if rec else ''
    except Exception:
        return ''


async def create_defect(data, creator_id: int) -> int:
    """Create a defect. Returns defect id."""
    case_name = ''
    case_uid = getattr(data, 'case_uid', None) or ''
    if case_uid:
        case_name = await _resolve_case_name(data.project_id, data.branch_id, case_uid)
    async with session_ctx() as session:
        defect = Defect(
            title=data.title,
            description=data.description or '',
            steps=data.steps or '',
            project_id=data.project_id,
            branch_id=data.branch_id,
            module_id=data.module_id or 0,
            severity=data.severity or 'P3',
            priority=data.priority or 'P3',
            status='unconfirmed',
            creator_id=creator_id,
            assignee_id=data.assignee_id or 0,
            case_uid=case_uid,
            case_name=case_name,
            bug_type=getattr(data, 'bug_type', None) or 'code_error',
            deadline=getattr(data, 'deadline', None) or '',
        )
        session.add(defect)
        await session.flush()
        defect_id = defect.id
        await session.commit()
        return defect_id


async def get_defect(defect_id: int) -> dict | None:
    """Get a defect by id. Returns dict or None."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Defect).where(Defect.id == defect_id)
        )
        defect = result.scalar_one_or_none()
        if defect is None:
            return None
        return _defect_to_dict(defect)


async def get_defects_by_case_uid(project_id: int, case_uid: str) -> list[dict]:
    """Get defects that reference a given test case (case_uid)."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Defect)
            .where(Defect.project_id == project_id, Defect.case_uid == case_uid)
            .order_by(desc(Defect.id))
        )
        return [_defect_to_dict(d) for d in result.scalars().all()]


async def get_defects(project_id: int, branch_id: int, status: str = None,
                      severity: str = None, priority: str = None,
                      module_id: int = None, assignee_id: int = None,
                      creator_id: int = None, search: str = None,
                      page: int = 1, page_size: int = 20) -> dict:
    """Get paginated defects with optional filters."""
    from sqlalchemy import func, or_
    async with session_ctx() as session:
        query = select(Defect).where(
            Defect.project_id == project_id,
            Defect.branch_id == branch_id,
        )
        count_q = select(func.count(Defect.id)).where(
            Defect.project_id == project_id,
            Defect.branch_id == branch_id,
        )

        if status:
            query = query.where(Defect.status == status)
            count_q = count_q.where(Defect.status == status)
        if severity:
            query = query.where(Defect.severity == severity)
            count_q = count_q.where(Defect.severity == severity)
        if priority:
            query = query.where(Defect.priority == priority)
            count_q = count_q.where(Defect.priority == priority)
        if module_id is not None:
            query = query.where(Defect.module_id == module_id)
            count_q = count_q.where(Defect.module_id == module_id)
        if assignee_id is not None:
            query = query.where(Defect.assignee_id == assignee_id)
            count_q = count_q.where(Defect.assignee_id == assignee_id)
        if creator_id is not None:
            query = query.where(Defect.creator_id == creator_id)
            count_q = count_q.where(Defect.creator_id == creator_id)
        if search:
            pattern = f'%{search}%'
            query = query.where(
                or_(
                    Defect.title.like(pattern),
                    Defect.description.like(pattern),
                )
            )
            count_q = count_q.where(
                or_(
                    Defect.title.like(pattern),
                    Defect.description.like(pattern),
                )
            )

        total = (await session.execute(count_q)).scalar() or 0

        offset = (page - 1) * page_size
        result = await session.execute(
            query.order_by(desc(Defect.id))
            .offset(offset)
            .limit(page_size)
        )
        defects = result.scalars().all()
        items = [_defect_to_dict(d) for d in defects]

        return {
            'total': total,
            'items': items,
            'page': page,
            'page_size': page_size,
            'pages': max(1, (total + page_size - 1) // page_size),
        }


async def update_defect(defect_id: int, data) -> bool:
    """Update a defect's editable fields. Returns True if updated."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Defect).where(Defect.id == defect_id)
        )
        defect = result.scalar_one_or_none()
        if defect is None:
            return False
        if data.title:
            defect.title = data.title
        if data.description is not None:
            defect.description = data.description
        if data.steps is not None:
            defect.steps = data.steps
        if data.module_id is not None:
            defect.module_id = data.module_id
        if data.severity:
            defect.severity = data.severity
        if data.priority:
            defect.priority = data.priority
        if data.assignee_id is not None:
            defect.assignee_id = data.assignee_id
        if getattr(data, 'case_uid', None) is not None:
            new_uid = data.case_uid or ''
            defect.case_uid = new_uid
            if new_uid:
                defect.case_name = await _resolve_case_name(
                    defect.project_id, defect.branch_id, new_uid
                )
            else:
                defect.case_name = ''
        if getattr(data, 'bug_type', None):
            defect.bug_type = data.bug_type
        if getattr(data, 'deadline', None) is not None:
            defect.deadline = data.deadline
        await session.commit()
        return True


async def transition_defect(defect_id: int, action: str, operator_id: int,
                            **kwargs) -> bool:
    """Apply a state machine transition to a defect. Returns True if successful."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Defect).where(Defect.id == defect_id)
        )
        defect = result.scalar_one_or_none()
        if defect is None:
            raise ValueError(f'缺陷不存在: {defect_id}')

        from app.api.defect_states import apply_transition
        transition = apply_transition(defect.status, action, **kwargs)

        # 确认缺陷时必须指派处理人（未确认状态仅能通过 confirm 确认）
        if action == 'confirm' and not kwargs.get('assignee_id'):
            raise ValueError('确认缺陷时必须指派处理人')

        old_status = defect.status
        old_resolution = defect.resolution
        defect.status = transition['status']
        defect.resolution = transition['resolution']

        # If assign action, update assignee
        if action == 'assign' and kwargs.get('assignee_id'):
            old_assignee = defect.assignee_id
            defect.assignee_id = kwargs['assignee_id']
            if old_assignee != defect.assignee_id:
                await _create_defect_log(session, defect_id, 'assignee_id',
                                          str(old_assignee), str(defect.assignee_id), operator_id)

        # If confirm action, update assignee, bug_type, priority, deadline
        if action == 'confirm':
            if kwargs.get('assignee_id'):
                old_assignee = defect.assignee_id
                defect.assignee_id = kwargs['assignee_id']
                if old_assignee != defect.assignee_id:
                    await _create_defect_log(session, defect_id, 'assignee_id',
                                              str(old_assignee), str(defect.assignee_id), operator_id)
            if kwargs.get('bug_type'):
                old_bug_type = defect.bug_type
                defect.bug_type = kwargs['bug_type']
                if old_bug_type != defect.bug_type:
                    await _create_defect_log(session, defect_id, 'bug_type',
                                              old_bug_type or '', defect.bug_type, operator_id)
            if kwargs.get('priority'):
                old_priority = defect.priority
                defect.priority = kwargs['priority']
                if old_priority != defect.priority:
                    await _create_defect_log(session, defect_id, 'priority',
                                              old_priority, defect.priority, operator_id)
            if kwargs.get('deadline') is not None:
                old_deadline = defect.deadline
                defect.deadline = kwargs['deadline']
                if old_deadline != defect.deadline:
                    await _create_defect_log(session, defect_id, 'deadline',
                                              old_deadline or '', defect.deadline, operator_id)

        # If resolve action, set resolved_version, resolved_date and assignee
        if action == 'resolve':
            resolved_version = kwargs.get('resolved_version', 0)
            if resolved_version:
                defect.resolved_version = resolved_version
            duplicate_defect_id = kwargs.get('duplicate_defect_id', 0)
            if duplicate_defect_id:
                defect.duplicate_defect_id = duplicate_defect_id
            from datetime import datetime
            defect.resolved_date = datetime.utcnow().isoformat()
            if kwargs.get('assignee_id'):
                old_assignee = defect.assignee_id
                defect.assignee_id = kwargs['assignee_id']
                if old_assignee != defect.assignee_id:
                    await _create_defect_log(session, defect_id, 'assignee_id',
                                              str(old_assignee), str(defect.assignee_id), operator_id)

        # If comment is provided, create it
        comment = kwargs.get('comment', '')
        if comment:
            from app.db.models import DefectComment as DefectCommentModel
            c = DefectCommentModel(
                defect_id=defect_id,
                content=comment,
                author_id=operator_id,
            )
            session.add(c)

        await session.commit()

        # Create log entries for status and resolution changes
        if old_status != defect.status:
            await _create_defect_log(session, defect_id, 'status',
                                      old_status, defect.status, operator_id)
        if defect.resolution and old_resolution != defect.resolution:
            await _create_defect_log(session, defect_id, 'resolution',
                                      old_resolution, defect.resolution, operator_id)

        return True


async def delete_defect(defect_id: int) -> bool:
    """Delete a defect and its attachments, logs and comments. Returns True if deleted."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Defect).where(Defect.id == defect_id)
        )
        defect = result.scalar_one_or_none()
        if defect is None:
            return False

        # Delete attachment, log and comment records
        await session.execute(
            delete(DefectAttachment).where(DefectAttachment.defect_id == defect_id)
        )
        await session.execute(
            delete(DefectLog).where(DefectLog.defect_id == defect_id)
        )
        await session.execute(
            delete(DefectComment).where(DefectComment.defect_id == defect_id)
        )
        # Delete the defect itself
        await session.execute(
            delete(Defect).where(Defect.id == defect_id)
        )
        await session.commit()
        return True


async def copy_defect(defect_id: int, operator_id: int) -> int:
    """Copy a defect. Returns new defect id.

    Copies: title, description, steps, severity, priority, module_id, bug_type, deadline
    Resets: status → unconfirmed
    Does not copy: created_at, updated_at, creator_id (set to operator)
    """
    async with session_ctx() as session:
        result = await session.execute(
            select(Defect).where(Defect.id == defect_id)
        )
        original = result.scalar_one_or_none()
        if original is None:
            raise ValueError(f'缺陷不存在: {defect_id}')

        new_defect = Defect(
            title=original.title,
            description=original.description or '',
            steps=original.steps or '',
            project_id=original.project_id,
            branch_id=original.branch_id,
            module_id=original.module_id,
            severity=original.severity,
            priority=original.priority,
            status='unconfirmed',
            creator_id=operator_id,
            assignee_id=0,
            bug_type=original.bug_type or 'code_error',
            deadline=original.deadline or '',
        )
        session.add(new_defect)
        await session.flush()
        new_id = new_defect.id
        await session.commit()
        return new_id


async def get_recent_defects(project_id: int, branch_id: int, limit: int = 2) -> list[dict]:
    """Get the most recent defects for a project and branch."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Defect)
            .where(Defect.project_id == project_id, Defect.branch_id == branch_id)
            .order_by(desc(Defect.id))
            .limit(limit)
        )
        defects = result.scalars().all()
        return [_defect_to_dict(d) for d in defects]


async def get_my_defects(user_id: int, project_id: int, branch_id: int) -> list[dict]:
    """Get defects assigned to or created by a user."""
    async with session_ctx() as session:
        result = await session.execute(
            select(Defect)
            .where(
                Defect.project_id == project_id,
                Defect.branch_id == branch_id,
                (Defect.assignee_id == user_id) | (Defect.creator_id == user_id),
            )
            .order_by(desc(Defect.id))
        )
        defects = result.scalars().all()
        return [_defect_to_dict(d) for d in defects]


def _defect_to_dict(d) -> dict:
    """Convert a Defect ORM object to a dict."""
    return {
        'id': d.id,
        'title': d.title,
        'description': d.description or '',
        'steps': d.steps or '',
        'project_id': d.project_id,
        'branch_id': d.branch_id,
        'module_id': d.module_id,
        'severity': d.severity,
        'priority': d.priority,
        'status': d.status,
        'resolution': d.resolution or '',
        'assignee_id': d.assignee_id,
        'creator_id': d.creator_id,
        'case_uid': d.case_uid or '',
        'case_name': d.case_name or '',
        'bug_type': d.bug_type or 'code_error',
        'deadline': d.deadline or '',
        'resolved_version': d.resolved_version or 0,
        'resolved_date': dt_iso_from_str(d.resolved_date),
        'created_at': dt_iso(d.created_at) if d.created_at else '',
        'updated_at': dt_iso(d.updated_at) if d.updated_at else '',
    }


# ── Defect Log CRUD ──


async def _create_defect_log(session, defect_id: int, field: str,
                              old_value: str, new_value: str, operator_id: int) -> int:
    """Internal helper to create a defect log entry within an existing session."""
    log = DefectLog(
        defect_id=defect_id,
        field=field,
        old_value=old_value or '',
        new_value=new_value or '',
        operator_id=operator_id,
    )
    session.add(log)
    await session.flush()
    return log.id


async def create_defect_log(defect_id: int, field: str, old_value: str,
                             new_value: str, operator_id: int) -> int:
    """Create a defect log entry. Returns log id."""
    async with session_ctx() as session:
        return await _create_defect_log(session, defect_id, field, old_value, new_value, operator_id)


async def get_defect_logs(defect_id: int) -> list[dict]:
    """Get all logs for a defect."""
    async with session_ctx() as session:
        result = await session.execute(
            select(DefectLog)
            .where(DefectLog.defect_id == defect_id)
            .order_by(DefectLog.id)
        )
        logs = result.scalars().all()
        return [
            {
                'id': log.id,
                'defect_id': log.defect_id,
                'field': log.field,
                'old_value': log.old_value or '',
                'new_value': log.new_value or '',
                'operator_id': log.operator_id,
                'created_at': dt_iso(log.created_at) if log.created_at else '',
            }
            for log in logs
        ]


async def get_recent_defect_logs(defect_id: int, limit: int = 3) -> list[dict]:
    """Get the most recent logs for a defect (newest first)."""
    async with session_ctx() as session:
        result = await session.execute(
            select(DefectLog)
            .where(DefectLog.defect_id == defect_id)
            .order_by(desc(DefectLog.id))
            .limit(limit)
        )
        logs = result.scalars().all()
        return [
            {
                'id': log.id,
                'field': log.field,
                'old_value': log.old_value or '',
                'new_value': log.new_value or '',
                'operator_id': log.operator_id,
                'created_at': dt_iso(log.created_at) if log.created_at else '',
            }
            for log in logs
        ]


# ── Defect Attachment CRUD ──


async def create_defect_attachment(defect_id: int, filename: str, filepath: str,
                                    file_size: int, mime_type: str, created_by: int) -> int:
    """Create a defect attachment record. Returns attachment id."""
    async with session_ctx() as session:
        attachment = DefectAttachment(
            defect_id=defect_id,
            filename=filename,
            filepath=filepath,
            file_size=file_size,
            mime_type=mime_type,
            created_by=created_by,
        )
        session.add(attachment)
        await session.flush()
        attachment_id = attachment.id
        await session.commit()
        return attachment_id


async def get_defect_attachment(attachment_id: int) -> dict | None:
    """Get a single attachment by id."""
    async with session_ctx() as session:
        result = await session.execute(
            select(DefectAttachment).where(DefectAttachment.id == attachment_id)
        )
        a = result.scalar_one_or_none()
        if a is None:
            return None
        return {
            'id': a.id,
            'defect_id': a.defect_id,
            'filename': a.filename,
            'filepath': a.filepath,
            'file_size': a.file_size,
            'mime_type': a.mime_type,
            'created_by': a.created_by,
            'created_at': dt_iso(a.created_at) if a.created_at else '',
        }


async def get_defect_attachments(defect_id: int) -> list[dict]:
    """Get all attachments for a defect."""
    async with session_ctx() as session:
        result = await session.execute(
            select(DefectAttachment)
            .where(DefectAttachment.defect_id == defect_id)
            .order_by(DefectAttachment.id)
        )
        attachments = result.scalars().all()
        return [
            {
                'id': a.id,
                'defect_id': a.defect_id,
                'filename': a.filename,
                'filepath': a.filepath,
                'file_size': a.file_size,
                'mime_type': a.mime_type,
                'created_by': a.created_by,
                'created_at': dt_iso(a.created_at) if a.created_at else '',
            }
            for a in attachments
        ]


async def delete_defect_attachment(attachment_id: int) -> bool:
    """Delete a defect attachment. Returns True if deleted."""
    async with session_ctx() as session:
        result = await session.execute(
            select(DefectAttachment).where(DefectAttachment.id == attachment_id)
        )
        attachment = result.scalar_one_or_none()
        if attachment is None:
            return False
        # Delete the physical file
        import os
        filepath = attachment.filepath
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        await session.execute(
            delete(DefectAttachment).where(DefectAttachment.id == attachment_id)
        )
        await session.commit()
        return True


# ── Defect Comment CRUD ──

async def create_defect_comment(defect_id: int, content: str, author_id: int) -> int:
    """Create a comment on a defect. Returns comment_id."""
    async with session_ctx() as session:
        comment = DefectComment(
            defect_id=defect_id,
            content=content,
            author_id=author_id,
        )
        session.add(comment)
        await session.flush()
        comment_id = comment.id
        await session.commit()
        return comment_id


async def get_defect_comments(defect_id: int) -> list[dict]:
    """Get all comments for a defect, enriched with author names."""
    async with session_ctx() as session:
        result = await session.execute(
            select(DefectComment)
            .where(DefectComment.defect_id == defect_id)
            .order_by(DefectComment.id)
        )
        comments = result.scalars().all()
        enriched = []
        for comment in comments:
            author_name = ''
            if comment.author_id:
                try:
                    user = await get_user_by_id(comment.author_id)
                    if user:
                        author_name = user.get('nickname', '')
                except Exception:
                    pass
            enriched.append({
                'id': comment.id,
                'defect_id': comment.defect_id,
                'content': comment.content,
                'author_id': comment.author_id,
                'author_name': author_name,
                'created_at': dt_iso(comment.created_at) if comment.created_at else '',
                'updated_at': dt_iso(comment.updated_at) if comment.updated_at else '',
            })
        return enriched


async def update_defect_comment(comment_id: int, content: str) -> bool:
    """Update a comment. Returns True if updated."""
    async with session_ctx() as session:
        result = await session.execute(
            select(DefectComment).where(DefectComment.id == comment_id)
        )
        comment = result.scalar_one_or_none()
        if comment is None:
            return False
        comment.content = content
        await session.commit()
        return True


async def delete_defect_comment(comment_id: int) -> bool:
    """Delete a comment. Returns True if deleted."""
    async with session_ctx() as session:
        result = await session.execute(
            delete(DefectComment).where(DefectComment.id == comment_id)
        )
        await session.commit()
        return result.rowcount > 0
