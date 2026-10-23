import pytest
from celery.exceptions import Retry

from app.core.logger import logger
from app.services.embedding import EmbeddingError
from app.tasks import embedding as embedding_tasks


@pytest.fixture
def retries(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record task.retry calls instead of talking to a broker; raises Retry like the real one."""
    calls: list[dict] = []

    def fake_retry(*, countdown: int, args: tuple, kwargs: dict) -> None:
        calls.append({"countdown": countdown, "args": args, "kwargs": kwargs})
        raise Retry()

    monkeypatch.setattr(embedding_tasks.embed_document, "retry", fake_retry)
    return calls


@pytest.fixture
def failed(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    calls: list[tuple[int, str]] = []

    async def mark_failed(document_id: int, error: str) -> None:
        calls.append((document_id, error))

    monkeypatch.setattr(embedding_tasks, "_mark_failed", mark_failed)
    return calls


def run_raising(monkeypatch: pytest.MonkeyPatch, error: EmbeddingError) -> None:
    async def run(_document_id: int) -> None:
        raise error

    monkeypatch.setattr(embedding_tasks, "_run", run)


@pytest.mark.parametrize(("attempt", "countdown"), [(0, 5), (1, 15), (2, 60)])
def test_retryable_error_retries_with_a_rising_delay(
    retries: list[dict],
    failed: list[tuple[int, str]],
    monkeypatch: pytest.MonkeyPatch,
    attempt: int,
    countdown: int,
) -> None:
    run_raising(monkeypatch, EmbeddingError("slow down", retryable=True))

    with pytest.raises(Retry):
        embedding_tasks.embed_document(4, "t", attempt)

    assert retries == [
        {"countdown": countdown, "args": (4, "t"), "kwargs": {"attempt": attempt + 1}}
    ]
    assert failed == []


def test_retries_exhausted_marks_failed_and_logs_a_warning(
    retries: list[dict], failed: list[tuple[int, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    records: list[dict] = []
    sink = logger.add(lambda m: records.append(m.record), level="WARNING")
    run_raising(monkeypatch, EmbeddingError("still down", retryable=True))

    embedding_tasks.embed_document(4, "t", 3)

    logger.remove(sink)
    assert retries == []
    assert failed == [(4, "still down")]
    assert [r["message"] for r in records] == ["embedding failed for document 4: still down"]


def test_permanent_error_fails_at_once(
    retries: list[dict], failed: list[tuple[int, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_raising(monkeypatch, EmbeddingError("bad key"))

    embedding_tasks.embed_document(4, "t")

    assert retries == []
    assert failed == [(4, "bad key")]


def test_success_neither_retries_nor_fails(
    retries: list[dict], failed: list[tuple[int, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run(_document_id: int) -> None:
        return None

    monkeypatch.setattr(embedding_tasks, "_run", run)

    embedding_tasks.embed_document(4, "t")

    assert retries == []
    assert failed == []
