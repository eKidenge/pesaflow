import logging

logger = logging.getLogger(__name__)


def send_notification(
    user=None,
    title="",
    message="",
    notification_type="info",
    metadata=None
):
    """
    Safe placeholder notification task.
    Prevents import errors and allows future async upgrade (Celery).
    """
    try:
        logger.info(
            f"Notification | user={user} | "
            f"title={title} | type={notification_type} | "
            f"message={message} | metadata={metadata}"
        )
        return True
    except Exception as e:
        logger.error(f"Notification error: {str(e)}")
        return False
