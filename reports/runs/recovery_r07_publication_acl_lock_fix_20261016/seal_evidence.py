"""Bind runtime bytes and command results without reading or exporting connection secrets."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAW = Path(__file__).resolve().parent
ROOT = RAW.parents[2]
BASELINE = "71e594cb958bd93d21fb7ed66574b3cba4cc47e1"
FREEZE = "a80408fb35addf35c04a91d255f20fb9a987423e"
baseline_record = json.loads((RAW / "baseline_original_probe9.json").read_text(encoding="utf-8"))
assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip() == FREEZE
source_files = (
    "backend/src/ai_intel/enrichment/inputs.py",
    "backend/src/ai_intel/enrichment/publication.py",
    "backend/tests/integration/test_r07_publication_acl_lock_fix_pg.py",
    "docs/decisions/CR-R07_multisource_enrichment_publication.md",
)
for relative in source_files:
    path = ROOT / relative
    (RAW / "byteblob" / (path.name + ".frozen")).write_bytes(path.read_bytes())
for relative, expected_hash in baseline_record["source_hashes"].items():
    relative = relative.replace("\\", "/")
    blob = subprocess.run(["git", "cat-file", "blob", BASELINE + ":" + relative], cwd=ROOT, capture_output=True, check=True).stdout
    candidates = (blob, blob.replace(b"\n", b"\r\n"))
    runtime_bytes = next(candidate for candidate in candidates if hashlib.sha256(candidate).hexdigest() == expected_hash)
    (RAW / "byteblob" / (Path(relative).name + ".baseline_runtime")).write_bytes(runtime_bytes)
unchanged = {}
for relative in (
    "backend/src/ai_intel/ingestion/source_documents.py",
    "backend/src/ai_intel/ingestion/catalog_documents.py",
    "backend/src/ai_intel/knowledge/revisions.py",
    "backend/src/ai_intel/knowledge/event_linking.py",
    "backend/src/ai_intel/knowledge/persistence.py",
    "backend/src/ai_intel/enrichment/signals.py",
    "backend/src/ai_intel/enrichment/signal_sources.py",
):
    before = subprocess.run(["git", "rev-parse", BASELINE + ":" + relative], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    after = subprocess.run(["git", "rev-parse", FREEZE + ":" + relative], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert before == after
    unchanged[relative] = {"git_blob_before": before, "git_blob_after": after, "runtime_sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}
results = []
for path in sorted(RAW.glob("*.json")):
    value = json.loads(path.read_text(encoding="utf-8"))
    if "argv" not in value:
        continue
    result = dict(name=path.stem, metadata=path.name, **value)
    xml_path = path.with_suffix(".xml")
    if xml_path.exists():
        cases = ET.parse(xml_path).getroot().findall(".//testcase")
        result["test_counts"] = {
            "total": len(cases),
            "failed": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }
    results.append(result)
manifest = {
    "sealed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
    "baseline_sha": BASELINE,
    "code_freeze_sha": FREEZE,
    "source_files": {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() for relative in source_files},
    "task_report": {"path": "reports/tasks/R07-publication-acl-lock-fix.md", "sha256": hashlib.sha256((ROOT / "reports/tasks/R07-publication-acl-lock-fix.md").read_bytes()).hexdigest()},
    "unchanged_shared_files": unchanged,
    "commands": results,
    "artifacts": {str(path.relative_to(RAW)): {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(RAW.rglob("*")) if path.is_file() and path.name != "raw_manifest.json" and "__pycache__" not in path.parts},
}
(RAW / "raw_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"freeze": FREEZE, "artifacts": len(manifest["artifacts"]), "commands": len(results), "sealed_at": manifest["sealed_at"]}, ensure_ascii=False))
