"""Verify this diagnostic run's saved command records and artifact boundaries."""

import json
from datetime import datetime, timedelta
from pathlib import Path


run_directory = Path(__file__).resolve().parent
records = json.loads((run_directory / "commands.json").read_text(encoding="utf-8-sig"))
assert len(records) == 25
assert len({record["probe_name"] for record in records}) == 25
for record in records:
    assert record["working_directory"] == "D:\\dianzi"
    assert 20 <= record["timeout_seconds"] <= 30
    assert datetime.fromisoformat(record["started_at"]).utcoffset() == timedelta(hours=8)
    assert datetime.fromisoformat(record["ended_at"]).utcoffset() == timedelta(hours=8)
    for stream_name in ("stdout_file", "stderr_file"):
        stream_path = run_directory / record[stream_name]
        assert stream_path.parent == run_directory and stream_path.is_file()
    if record["timed_out"]:
        assert record["exit_code"] == 124 and record["actual_process_exit_code"] != 0
by_name = {record["probe_name"]: record for record in records}
assert by_name["docker_engine_final"]["timed_out"]
assert by_name["socket_isolation"]["exit_code"] == 1
isolation = json.loads((run_directory / "socket_isolation.stdout.log").read_text(encoding="utf-8-sig"))
assert isolation["moved"] is False and isolation["original_still_exists"] is True
assert isolation["backup_exists"] is False
metadata = json.loads((run_directory / "socket_reparse_tag.stdout.log").read_text(encoding="utf-8-sig"))
assert metadata["reparse_tag"] == "0x80000023" and metadata["is_name_surrogate"] is False
assert metadata["resolved_path"] == "C:\\Users\\yinha\\AppData\\Local\\Docker\\run\\dockerInference"
assert metadata["length_bytes"] == 0 and metadata["link_target"] is None
print("Evidence assertions passed: 25 command records, retained listener, bounded probes, existing logs.")
