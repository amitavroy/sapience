import sys

from loguru import logger

from app.core.config import settings

_HUMAN_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<magenta>{extra[trace_id]}</magenta> - <level>{message}</level>"
)

logger.remove()
logger.configure(extra={"trace_id": "-"})  # lines outside a request still format
logger.add(
    sys.stderr,
    level="DEBUG" if settings.debug else "INFO",
    enqueue=True,
    format=_HUMAN_FORMAT,
    serialize=not settings.debug,  # JSON (trace_id under record.extra) in prod
)

__all__ = ["logger"]
