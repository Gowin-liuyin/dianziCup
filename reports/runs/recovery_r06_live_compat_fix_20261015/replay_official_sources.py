"""Replay existing external originals in memory; never export the original record body."""

import base64
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.ingestion.catalog_pages import normalize_avid_blob, normalize_catalog_page, select_avid_blob

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def current_time():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started_at = current_time()
manifest = json.loads((RUN / "official_response_manifest.json").read_text(encoding="utf-8"))
results = []
for entry in manifest:
    body = Path(entry["original_path"]).read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    expected = Path(entry["original_path"]).stem.rsplit("-", 1)[-1]
    assert digest == expected
    row = {"source_kind": entry["source_kind"], "raw_sha256": digest,
           "response_bytes": len(body), "original_path": entry["original_path"]}
    try:
        if entry["source_kind"] == "ollama_releases":
            page = normalize_catalog_page(entry["source_kind"], body, entry["cursor"], entry["headers"])
            assert len(page.documents) == 20 and page.next_cursor == {"page": 2}
            original_items = json.loads(body)
            assert [json.loads(member.payload) for member in page.documents] == original_items
            assert all(member.parsed.status == "parsed" for member in page.documents)
            assert all(member.metadata["risk_status"] == "not_assessed" for member in page.documents)
            row.update({"verdict": "passed", "documents": 20, "next_cursor": page.next_cursor,
                        "all_original_fields_preserved": True, "all_parsed": True,
                        "vulnerability_assessment": "not_assessed"})
        else:
            tree_body = Path(entry["tree_path"]).read_bytes()
            tree_digest = hashlib.sha256(tree_body).hexdigest()
            assert tree_digest == "0c04c3689ee1cd32714083b8e066c8f10c06439ebd2b0c7a10b9a2c4ecb4b5e5"
            selection = select_avid_blob(tree_body, entry["cursor"])
            assert selection is not None
            member = normalize_avid_blob(selection, body)
            envelope = json.loads(body)
            payload = base64.b64decode(envelope["content"].replace("\n", ""), validate=True)
            assert member.payload == payload
            assert member.source_record_id == "AVID-2023-V027"
            assert member.parsed.status == "parsed"
            assert member.metadata["referenced_advisory_ids"] == []
            assert member.metadata["source_adapter_version"] == "catalog-pages-3"
            assert any("未获取或读取图片" in note for note in member.metadata["source_notes"])
            assert selection.next_cursor["record_offset"] == 2
            row.update({"verdict": "passed", "documents": 1, "source_record_id": member.source_record_id,
                        "decoded_sha256": hashlib.sha256(payload).hexdigest(),
                        "git_tree_sha": selection.tree_sha, "git_blob_sha": selection.blob_sha,
                        "tree_response_sha256": tree_digest, "original_payload_preserved": True,
                        "referenced_advisory_ids": [], "screenshot_fetched": False,
                        "source_adapter_version": member.metadata["source_adapter_version"],
                        "next_cursor": selection.next_cursor})
    except Exception as error:
        row.update({"verdict": "failed", "exception_type": type(error).__name__})
    results.append(row)
source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in [ROOT / "backend/src/ai_intel/ingestion/catalog_pages.py",
                              ROOT / "backend/src/ai_intel/ingestion/sources/github_releases.py",
                              ROOT / "backend/src/ai_intel/ingestion/sources/avid_records.py"]}
exit_code = 0 if all(row["verdict"] == "passed" for row in results) else 1
output = {"classification": "offline original response replay; not live execution",
          "base_sha": "1a52e17ffe327fb8a0c1d4f97372948a699910e3", "source_hashes": source_hashes,
          "argv": sys.argv, "cwd": os.getcwd(), "runtime_executable": sys.executable,
          "started_at": started_at, "finished_at": current_time(), "results": results,
          "network_requests": 0, "database_calls": 0, "model_calls": 0, "exit_code": exit_code}
(RUN / "official_replay.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
print(json.dumps(output, indent=2))
raise SystemExit(exit_code)
