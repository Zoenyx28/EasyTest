"""Shared Celery application; API processes only enqueue work."""
from __future__ import annotations

from celery import Celery

from app.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

broker_url = CELERY_BROKER_URL
result_backend = CELERY_RESULT_BACKEND

celery_app = Celery('test_platform', broker=broker_url, backend=result_backend)
celery_app.conf.update(
    task_default_queue='test-execution',
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    timezone='Asia/Shanghai',
)
celery_app.autodiscover_tasks(['app.scheduler'])
