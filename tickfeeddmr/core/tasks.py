from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def ping() -> str:
    """Тривиальная задача для smoke-проверки Celery."""
    logger.info("Celery smoke-проверка: задача ping выполнена")
    return "pong"
