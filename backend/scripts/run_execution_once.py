"""Windows-friendly one-shot worker for an already-created execution.

Celery's prefork worker is not reliable as a detached Windows process.  This
utility executes the same worker entry point and is useful for local validation
while production continues to use the Docker Celery workers.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import crud
from app.services.executor import execution_manager


async def execute(execution_id: str, concurrency: int, environment: str) -> None:
    uids = [case['uid'] for case in await crud.get_all_execution_case_uids(execution_id)]
    await execution_manager.run_in_worker(execution_id, uids, concurrency, environment)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('execution_id')
    parser.add_argument('--concurrency', type=int, default=3)
    parser.add_argument('--env', default='test')
    args = parser.parse_args()
    asyncio.run(execute(args.execution_id, args.concurrency, args.env))


if __name__ == '__main__':
    main()
