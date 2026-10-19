"""Check source and all author proof against raw and LF Git blob hashes separately."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
SOURCE = "592b49d6920a4b25db094212eab1d74ca964b1c2"
MATERIAL = "6472d816471a8c8ff176745d199ae4a3ef73270f"
AUTHOR_PATH = ROOT / "reports/runs/recovery_r17_event_detail_ui_fix1_20261016/artifact_manifest.json"
manifest = json.loads(AUTHOR_PATH.read_text(encoding="utf-8"))
rows = []
for scope in ["source_files", "evidence_files"]:
    for record in manifest[scope]:
        ref = SOURCE if scope == "source_files" else MATERIAL
        result = subprocess.run(["git", "cat-file", "blob", f"{ref}:{record['path']}"], cwd=ROOT, capture_output=True, check=True)
        local = (ROOT / record["path"]).read_bytes()
        blob = result.stdout
        sha = lambda content: hashlib.sha256(content).hexdigest()
        row = dict(scope=scope, path=record["path"], git_ref=ref, expected_raw_sha256=record["sha256"], expected_lf_sha256=record.get("sha256_lf"), git_blob_bytes=len(blob), local_bytes=len(local), git_blob_raw_sha256=sha(blob), local_raw_sha256=sha(local), git_blob_lf_sha256=sha(blob.replace(b"\r\n", b"\n")), local_lf_sha256=sha(local.replace(b"\r\n", b"\n")), git_raw_match=sha(blob) == record["sha256"], local_raw_match=sha(local) == record["sha256"])
        row["git_lf_match"] = record.get("sha256_lf") == row["git_blob_lf_sha256"] if "sha256_lf" in record else None
        row["local_lf_match"] = record.get("sha256_lf") == row["local_lf_sha256"] if "sha256_lf" in record else None
        row["valid"] = (row["git_raw_match"] or row["git_lf_match"]) and (row["local_raw_match"] or row["local_lf_match"])
        rows.append(row)
report = dict(created_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), source_commit=SOURCE, material_commit=MATERIAL, sources=len(manifest["source_files"]), evidence=len(manifest["evidence_files"]), invalid=[row["path"] for row in rows if not row["valid"]], git_raw_match_count=sum(row["git_raw_match"] for row in rows), local_raw_match_count=sum(row["local_raw_match"] for row in rows), rows=rows)
(RUN / "author-manifest-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False))
assert report["sources"] == 2 and report["evidence"] == 66 and not report["invalid"]
