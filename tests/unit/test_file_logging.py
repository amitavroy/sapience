import json
from datetime import date
from pathlib import Path

from app.core.logger import add_file_sink, logger


def _log_warning_only(tmp_path: Path, serialize: bool) -> Path:
    sink = add_file_sink(tmp_path, "WARNING", 14, serialize=serialize)
    with logger.contextualize(trace_id="-"):  # isolate from ids leaked by other tests
        logger.info("skip me")
        logger.warning("keep me")
    logger.remove(sink)  # drains the enqueue queue
    return tmp_path / f"{date.today():%Y-%m-%d}.log"


def test_file_sink_writes_only_at_or_above_level_to_date_named_file(tmp_path: Path):
    path = _log_warning_only(tmp_path, serialize=False)

    assert path.exists()
    text = path.read_text()
    assert "keep me" in text
    assert "skip me" not in text
    assert "| - - keep me" in text  # default trace id


def test_file_sink_serialize_writes_one_json_object_per_line(tmp_path: Path):
    path = _log_warning_only(tmp_path, serialize=True)

    lines = path.read_text().splitlines()
    assert lines
    records = [json.loads(line)["record"] for line in lines]
    assert all(r["level"]["name"] == "WARNING" for r in records)
    assert records[0]["extra"]["trace_id"] == "-"
