import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings

_HUMAN_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<magenta>{extra[trace_id]}</magenta> - <level>{message}</level>"
)

_PLAIN_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | "
    "{extra[trace_id]} - {message}"
)


def add_file_sink(log_dir: str | Path, level: str, retention_days: int, serialize: bool) -> int:
    """One file per day, e.g. logs/2026-10-19.log; returns the sink id."""
    return logger.add(
        Path(log_dir) / "{time:YYYY-MM-DD}.log",
        level=level,
        rotation="00:00",  # new date-named file at midnight
        retention=f"{retention_days} days" if retention_days else None,
        enqueue=True,
        format=_PLAIN_FORMAT,
        colorize=False,
        serialize=serialize,
        encoding="utf-8",
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
if settings.log_file_level:
    add_file_sink(
        settings.log_dir,
        settings.log_file_level,
        settings.log_file_retention_days,
        serialize=not settings.debug,
    )

__all__ = ["logger"]
