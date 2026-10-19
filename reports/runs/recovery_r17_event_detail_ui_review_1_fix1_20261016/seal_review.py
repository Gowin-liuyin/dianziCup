"""Seal directed review evidence and emit a separate hash of the manifest bytes."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import base64
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
SOURCE = "592b49d6920a4b25db094212eab1d74ca964b1c2"
MATERIAL = "6472d816471a8c8ff176745d199ae4a3ef73270f"
REPORT = ROOT / "reports/reviews/recovery/G-E-R17-event-detail-ui-review-1-recheck.md"
browser = json.loads((RUN / "browser.json").read_text(encoding="utf-8"))
probe = json.loads((RUN / "browser-probes.json").read_text(encoding="utf-8"))
unit = json.loads((RUN / "events-tests.json").read_text(encoding="utf-8"))
audit = json.loads((RUN / "author-manifest-audit.json").read_text(encoding="utf-8"))
metrics = []
def collect(value):
    if isinstance(value, dict):
        if isinstance(value.get("name"), str) and value["name"].startswith("fact-target-metrics-"):
            metrics.append(json.loads(base64.b64decode(value["body"])))
        for item in value.values():
            collect(item)
    elif isinstance(value, list):
        for item in value:
            collect(item)
collect(browser)
assert sorted(item["width"] for item in metrics) == [390, 1366]
for item in metrics:
    height = 44 if item["width"] == 390 else 40
    assert all(target["bounds"]["height"] == height and target["minHeight"] == f"{height}px" for target in item["factTargetMetrics"])
(RUN / "target-size-summary.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
assert not audit["invalid"] and audit["sources"] == 2 and audit["evidence"] == 66
assert unit["numPassedTests"] == 30 and unit["numFailedTests"] == 0
assert browser["stats"]["expected"] == 7 and probe["stats"]["expected"] == 3
assert not browser["stats"]["unexpected"] and not probe["stats"]["unexpected"]
assert hashlib.sha256((RUN / "review-fixture-probes.spec.ts").read_bytes()).hexdigest() == "999901b621a1e59f927e5937e0ad20219faf40253be2a892ac5d90207c70aa05"
commands = [json.loads(line) for line in (RUN / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
assert all(not item["listener_after"] for item in commands if item["label"].endswith("controlledserve-end"))
tracked = subprocess.run(["git", "diff", "--name-only", MATERIAL], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8").splitlines()
assert not tracked
def artifact(path):
    content = path.read_bytes()
    record = dict(path=path.relative_to(ROOT).as_posix(), bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    try:
        content.decode("utf-8")
        record["sha256_lf"] = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
    except UnicodeDecodeError:
        pass
    return record
files = sorted(path for path in RUN.rglob("*") if path.is_file() and path.name not in ["artifact_manifest.json", "artifact_manifest.sha256"]) + [REPORT]
manifest = dict(task="R17 event detail UI review 1 directed fix1 recheck", verdict="Ship limited schema2 slice", created_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), source_commit=SOURCE, material_commit=MATERIAL, tracked_unchanged=True, author_manifest_counts=dict(sources=2, evidence=66, invalid=0, git_raw_match=58, local_raw_match=46), unit=dict(total=30, passed=30, failed=0, skipped=0), fixture_browser=dict(original_independent_3=probe["stats"], original_browser_7=browser["stats"], target_sizes=[dict(width=item["width"], count=len(item["factTargetMetrics"]), height=44 if item["width"] == 390 else 40) for item in metrics]), full_352_regression="not_run", real_backend_integration="not_run", live="not_run", native_hidden="not_run", whole_R17="partial_not_accepted", own_port=25321, final_listener=False, boundary=dict(secret_reads=0, external_requests=0, model_calls=0, CNNVD_tab_touches=0, commit="not_run", push="not_run"), evidence_files=[artifact(path) for path in files])
manifest_path = RUN / "artifact_manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
(RUN / "artifact_manifest.sha256").write_text(f"{digest}  artifact_manifest.json\n", encoding="ascii")
print(json.dumps(dict(created_at=manifest["created_at"], verdict=manifest["verdict"], source=SOURCE, material=MATERIAL, manifest_sha256=digest, evidence_count=len(files), target_sizes=manifest["fixture_browser"]["target_sizes"], raw_audit_invalid=0), ensure_ascii=False))
