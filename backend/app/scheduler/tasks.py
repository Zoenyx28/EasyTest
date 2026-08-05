"""Worker-side tasks.  This module is never executed by FastAPI directly."""
from __future__ import annotations

import asyncio

from app.scheduler.celery_app import celery_app
from app.services.executor import execution_manager


@celery_app.task(bind=True, name='test_platform.execute')
def execute_test_task(self, execution_id: str, uids: list[str], concurrency: int,
                      env: str = 'test', smoke_only: bool = False,
                      sequential: bool = False) -> dict:
    """Run one EasyTestcess in a Celery worker and persist its state."""
    return asyncio.run(execution_manager.run_in_worker(
        execution_id=execution_id,
        uids=uids,
        concurrency=concurrency,
        env=env,
        smoke_only=smoke_only,
        sequential=sequential,
    ))
