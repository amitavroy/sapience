# Daily log files with a configurable minimum level (GH-2)

## To-do

Each slice ends in a working, reviewable state. Pause for review after each slice.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | File sink | `log_dir`, `log_file_level`, `log_file_retention_days` settings in `app/core/config.py` | [ ] |
| 1 | File sink | `logger.py`: `_PLAIN_FORMAT`, `add_file_sink()`, called when `log_file_level` is set | [ ] |
| 1 | File sink | `tests/unit/test_file_logging.py`: threshold, date filename, JSON mode | [ ] |
| 2 | Config housekeeping | `.env.example` entries, `logs/` in `.gitignore`, `LOG_FILE_LEVEL=""` default in `tests/conftest.py` | [ ] |
| 3 | Docs | Wiki "Logging and trace id": file sink bullets (path, threshold, retention, off by default, format, Docker volume note) | [ ] |

## Context

Logs go only to stderr (`app/core/logger.py`). We want them in files too, one file per day (`logs/2026-10-19.log`) so no single file grows huge, with a setting for the lowest level that reaches the file. The API (`app/main.py`, `app/middleware/request_log.py`), the Celery worker (`app/tasks/*`) and the CLI (`app/cli/__main__.py`) all import `app.core.logger`, so one sink added there covers all three. Builds on GH-3 (trace id logging, plan 003).

## Decisions

1. **No new dependency:** loguru already does date-named files, rotation and retention.
2. **Filename:** `{log_dir}/{time:YYYY-MM-DD}.log` with `rotation="00:00"`. At midnight the sink opens a new file named after the new date. Because the name changes, the old file is never renamed.
3. **Level is a minimum threshold:** `LOG_FILE_LEVEL=WARNING` writes WARNING, ERROR and CRITICAL. This matches loguru's `level=` semantics and covers "info / warnings / errors". The `Literal` type makes a typo fail at startup instead of being silently ignored.
4. **Off by default:** an empty `LOG_FILE_LEVEL` adds no sink, so behaviour is unchanged until it is set. `.env.example` sets `INFO` so new setups get files.
5. **Retention:** `LOG_FILE_RETENTION_DAYS=14` by default; 0 means keep forever (`retention=None`). loguru globs the templated filename, so it finds older date files.
6. **Multiple processes:** files open in append mode. The API and worker each open the same day's file and append to it, and a restart on the same day continues that file. `enqueue=True` keeps writes off the caller's thread, as the stderr sink already does.
7. **Format:** same rule as stderr. When `DEBUG=true` it is plain text (`_HUMAN_FORMAT` without color tags) with the trace id. Otherwise it is one JSON object per line (`serialize=True`), with the trace id under `record.extra.trace_id`. `colorize=False` and `encoding="utf-8"`.
8. **Testability:** the sink lives in `add_file_sink(...)`, which returns the sink id. Tests call it with `tmp_path` and do not depend on module-import side effects.
9. **Tests never write to `logs/`:** `conftest.py` sets `os.environ.setdefault("LOG_FILE_LEVEL", "")` before importing settings. It also sets env vars with `setdefault`, which takes precedence over `.env`, so a developer's `.env` can't enable file logging during tests.

## Code

`app/core/config.py`:

```python
from typing import Literal


class Settings(BaseSettings):
    ...
    debug: bool = False
    log_dir: str = "logs"
    # lowest level written to the daily log file; empty = no file logging
    log_file_level: Literal["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = ""
    log_file_retention_days: int = 14  # 0 = keep forever
```

`app/core/logger.py`:

```python
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings

_HUMAN_FORMAT = ...  # unchanged
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
logger.configure(extra={"trace_id": "-"})
logger.add(sys.stderr, ...)  # unchanged
if settings.log_file_level:
    add_file_sink(
        settings.log_dir,
        settings.log_file_level,
        settings.log_file_retention_days,
        serialize=not settings.debug,
    )
```

`.env.example`:

```
# Daily log files: <LOG_DIR>/YYYY-MM-DD.log
LOG_DIR=logs
# Lowest level written to the file (DEBUG, INFO, WARNING, ERROR, CRITICAL). Empty = no file logging.
LOG_FILE_LEVEL=INFO
# Days of log files to keep; 0 = keep forever
LOG_FILE_RETENTION_DAYS=14
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `app/core/config.py` | 1 | Three log-file settings |
| `app/core/logger.py` | 1 | `_PLAIN_FORMAT`, `add_file_sink`, conditional sink |
| `tests/unit/test_file_logging.py` (new) | 1 | File sink tests |
| `.env.example` | 2 | Document the settings |
| `.gitignore` | 2 | Ignore `logs/` |
| `tests/conftest.py` | 2 | Keep file logging off in tests |
| `docs/wiki/index.md` | 3 | Logging section update |

## Testing plan

- **Threshold:** call `add_file_sink(tmp_path, "WARNING", 14, serialize=False)`, log `info("skip me")` and `warning("keep me")`, then call `logger.remove(sink)`, which drains the enqueue queue. Expect `tmp_path / f"{date.today():%Y-%m-%d}.log"` to exist and contain `keep me` but not `skip me`. The trace id `-` should appear on the line.
- **JSON mode:** the same call with `serialize=True`. Every line should parse with `json.loads`, and `record.level.name == "WARNING"`.
- **No file when off:** with `log_file_level=""`, importing the logger adds no file sink. This is covered implicitly because tests never create `logs/`. Add an explicit check only if it is cheap.
- The existing suites that capture loguru sinks (`tests/integration/test_trace.py`, `test_jobs.py`, `tests/unit/test_google_chat_task.py`) must keep passing.

## Verification

- `make test` and `make format` are clean.
- Set `LOG_FILE_LEVEL=INFO` in `.env`, run `make dev`, then `curl localhost:8000/health`. `logs/<today>.log` should have the request line with its trace id.
- Set `LOG_FILE_LEVEL=WARNING` and restart. A new health request should not be added to the file.
- Run `make worker` and trigger a job. Worker lines should land in the same daily file.
- Set `DEBUG=true`: file lines should be plain text. Set `DEBUG=false`: file lines should be JSON.
- Known limit: inside Docker, files go to `/srv/logs` and are lost with the container unless a volume is mounted there. This is documented in the wiki and is not changed in compose.
