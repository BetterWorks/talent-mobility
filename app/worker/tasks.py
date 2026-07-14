import logging

from app.celery_app import celery_app
from app.services.matching import run_ai_match


LOGGER = logging.getLogger(__name__)


@celery_app.task
def run_ai_match_task(run_id, request_id):
    from app.celery_app import get_event_loop
    loop = get_event_loop()
    loop.run_until_complete(run_ai_match(run_id=run_id, request_id=request_id))
