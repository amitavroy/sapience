import pytest

from app.agent import checkpointer
from app.core.config import settings


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "postgresql+asyncpg://u:p@localhost:5432/db",
            "postgresql://u:p@localhost:5432/db",
        ),
        ("postgresql://u:p@localhost/db", "postgresql://u:p@localhost/db"),
    ],
)
def test_conninfo_strips_the_asyncpg_driver(
    monkeypatch: pytest.MonkeyPatch, url: str, expected: str
) -> None:
    monkeypatch.setattr(settings, "database_url", url)
    assert checkpointer.conninfo() == expected
