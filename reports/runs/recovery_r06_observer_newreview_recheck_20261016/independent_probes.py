"""Retained 21 cases with independently approved safe-projection expectations."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
RUN = BASE / sys.argv[1] if len(sys.argv) > 1 else BASE
RUN.mkdir(exist_ok=True)
PREP = BASE.parent / "recovery_r06_incremental_observation_preparation_20261016"
sys.path.insert(0, str(PREP))
import observation_log as log

RETAINED = PREP / "original_negative_probes.py.txt"
SOURCE_HASH = "b0a8efd6a520f16b91bcf807f62c1570127d94ac142aeeb3abc35488a50b4f8e"
CODE = "1c4cce9770bfa29d08728a0131f7fc7fe714f9bc"
OLD = Path("D:/dianzi/reports/runs/recovery_gb_controlled_collection_20261015")
KEYS = {"jobs": ("job_id",), "fetches": ("attempt_id",), "page_receipts": ("source_id", "stream_kind", "page_key"), "cursors": ("source_id", "stream_kind"), "source_summary": ("source_id",), "publication_time_quality": ("source_id",)}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def fingerprint(value: dict) -> dict:
    result = copy.deepcopy(value)
    for row in result["cursors"]:
        position = row["cursor_json"]["position"]
        for key in ("after", "page_token"):
            if key in position:
                raw = position.pop(key).encode("utf-8")
                position[key + "_opaque"] = {"sha256": hashlib.sha256(raw).hexdigest(), "utf8_bytes": len(raw)}
    for table, fields in KEYS.items():
        result[table] = sorted(result[table], key=lambda row: tuple(row[key] for key in fields))
    return result


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def independent_legacy(record) -> None:
    source = OLD / "collection_observations.jsonl"
    before = file_hash(source)
    receipt = json.loads((OLD / "window_interruption_receipt.json").read_bytes())
    root = RUN / "independent21/legacy_safe_projection"
    writer = log.Journal(root, receipt["code_sha"], CODE, "legacy-recheck", "offline-projection")
    expected = []
    last = None
    kinds = {}
    with source.open("rb") as stream:
        for line in stream:
            raw = json.loads(line)
            projected = fingerprint(raw)
            encoded = writer.observe(log.validate_observation(raw))
            expected.append(hashlib.sha256(canonical(projected)).hexdigest())
            kinds[encoded["kind"]] = kinds.get(encoded["kind"], 0) + 1
            last = projected
    writer.finish(last, "offline_legacy_replay_complete", projected=True)
    state = {}
    index = 0
    previous_hash = "0" * 64
    for line in writer.path.open("rb"):
        item = json.loads(line)
        assert item["seq"] == index + 1 and item["previous_record_sha256"] == previous_hash
        payload = {key: value for key, value in item.items() if key != "record_sha256"}
        previous_hash = hashlib.sha256(canonical(payload)).hexdigest()
        assert previous_hash == item["record_sha256"]
        if item["kind"] in ("snapshot", "terminal"):
            state = item["observation"]
        elif item["kind"] == "delta":
            for key, changed in item["changes"].items():
                if key not in KEYS:
                    state[key] = changed
                    continue
                keys = KEYS[key]
                rows = {tuple(row[field] for field in keys): row for row in state[key]}
                for deleted in changed["deletes"]:
                    del rows[tuple(deleted)]
                for row in changed["upserts"]:
                    rows[tuple(row[field] for field in keys)] = row
                state[key] = list(rows.values())
        state["observed_at"] = item["observed_at"]
        for table, fields in KEYS.items():
            state[table] = sorted(state[table], key=lambda row: tuple(row[key] for key in fields))
        digest = hashlib.sha256(canonical(state)).hexdigest()
        assert digest == item["state_sha256"]
        if item["kind"] != "terminal":
            assert digest == expected[index]
        index += 1
    assert len(expected) == 369 and index == 370 and state == last
    assert log.replay(writer.path).observation == last
    after = file_hash(source)
    assert before == after == "012e5354d35c8eb8c55aa0adfcbf8555714412c7a1c3c111d82ddaa53ac3524f"
    evidence = {"input_rounds": 369, "independent_safe_projection_checks": 369, "source_sha256_before": before, "source_sha256_after": after, "source_bytes": source.stat().st_size, "old_product_sha": receipt["code_sha"], "observer_sha": CODE, "old_wall_seconds": receipt["actual_wall_seconds"], "written_kinds": kinds, "journal_bytes": writer.path.stat().st_size, "persistent_bytes": sum(path.stat().st_size for path in root.iterdir()), "operational_tokens_reconstructed": False, "new_live_seconds": 0}
    (RUN / "legacy_projection_receipt.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    record("369 legacy states independently rebuilt", "369 independently calculated public safe projections, not raw token equality", evidence, True)


def main() -> None:
    body = RETAINED.read_bytes()
    assert hashlib.sha256(body).hexdigest() == SOURCE_HASH
    namespace = {"__file__": str(RETAINED), "__name__": "independent_retained"}
    relative = "../" + RUN.relative_to(PREP.parent).as_posix() + "/independent21"
    with patch.object(sys, "argv", [str(RETAINED), relative]):
        exec(compile(body, str(RETAINED), "exec"), namespace)
    assert Path(namespace["RUN"]).resolve() == RUN / "independent21"
    independent_legacy(namespace["record"])
    for name in ("metadata_probes", "secret_and_validation_probes", "observer_shutdown_probes", "large_valid_delta_probe"):
        namespace[name]()
    records = namespace["checks"]
    original = json.loads(Path("D:/wt/r06-newrev/reports/runs/recovery_r06_observer_newreview_20261016/probe_retry4/negative_probes.json").read_bytes())["records"]
    assert len(records) == len(original) == 21
    assert [item["name"] for item in records] == [item["name"] for item in original]
    mappings = []
    for prior, current in zip(original, records, strict=True):
        migration = "unchanged observable expectation"
        if current["name"] == "369 legacy states independently rebuilt":
            migration = "root-approved safe projection and independently computed SHA256/length replace operational token equality"
        elif current["name"] == "cursor printable URL canary":
            migration = "valid operational token accepted, but no raw value written; original privacy assertion retained"
        mappings.append({"case": current["name"], "original_passed": prior["passed"], "current_passed": current["passed"], "original_expected": prior["expected"], "mapping": migration, "actual": current["actual"]})
    result = {"retained_script_sha256": SOURCE_HASH, "loaded_code_sha": CODE, "original_total": 21, "original_passed": 15, "original_failed": 6, "current_total": 21, "current_passed": sum(item["passed"] for item in records), "current_failed": sum(not item["passed"] for item in records), "skipped": 0, "mappings": mappings}
    (RUN / "independent21_mapping.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "mappings"}))
    assert result["current_passed"] == 21


if __name__ == "__main__":
    main()
