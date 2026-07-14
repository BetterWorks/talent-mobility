import asyncio
import logging
from asyncio import AbstractEventLoop
from typing import Optional

from celery import Celery
from celery.signals import task_failure, task_prerun, worker_process_init, worker_process_shutdown

from app import settings
from app.db import init_db
from app.utils.logs import add_common_context_args, agent


log = logging.getLogger(__name__)

celery_app = Celery('internal-mobility-matching')

celery_app.conf.update(
    broker_url=settings.REDIS_BROKER_URL,
    result_backend=settings.CELERY_DATABASE_BACKEND_URL,
    task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
    database_table_schemas={
        'task': settings.DATABASE_SCHEMA,
        'group': settings.DATABASE_SCHEMA,
    },
    database_table_names=settings.CELERY_RESULT_TABLES,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_extended=True,
    enable_utc=True,
    worker_log_format='%(message)s',
    broker_connection_retry_on_startup=True
)

celery_app.autodiscover_tasks(
    packages=['app.worker'],
    related_name='tasks',
    force=True
)

_loop: Optional[AbstractEventLoop] = None


def get_event_loop() -> AbstractEventLoop:
    if not _loop:
        log.error('Unable to get event loop!')
        raise RuntimeError

    return _loop


async def do_init_worker():
    await init_db()


@worker_process_init.connect
def init_worker(**_kwargs):
    log.info('Initialize worker...')

    global _loop
    _loop = asyncio.get_event_loop()
    _loop.run_until_complete(do_init_worker())
    log.info('Worker ready!')


@worker_process_shutdown.connect
def shutdown_worker(**_kwargs):
    log.info('Shutdown worker')
    global _loop
    if _loop:
        _loop.close()


@task_prerun.connect
def task_prerun_handler(task_id, task, kwargs, *_args, **_kwargs):
    add_common_context_args(
        task_id=task_id,
        task_name=task.name,
    )


@task_failure.connect
def task_failure_handler(exception, *_args, **_kwargs):
    logger = agent.get_context_bound_logger()
    logger.error(f"Task execution failed: {exception}", exc_info=True)
