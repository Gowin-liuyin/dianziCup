"""Record explicit review deliverables and frozen source inputs without caches."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

directory = Path(__file__).resolve().parent
source = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-tls\dianzi")
report = directory.parents[1] / "reviews/recovery/G-A-R01-search-TLS-review-1.md"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
git_status = subprocess.run(["git", "status", "--porcelain"], cwd=source, capture_output=True, text=True, check=True)
paths = [
    source / "backend/src/ai_intel/api/app.py",
    source / "backend/src/ai_intel/infrastructure/settings.py",
    source / "backend/tests/conftest.py",
    source / "backend/tests/integration/test_r01_search_tls_live.py",
    source / "backend/tests/contract/test_r01_compose_configuration.py",
    source / "backend/tests/contract/test_r01_search_tls_deployment.py",
    source / "infra/compose/README.md",
    source / "infra/compose/compose.yaml",
    source / "infra/compose/test.override.yaml",
    source / "infra/compose/opensearch/opensearch.yml",
    source / "infra/compose/compose.search.secure.host.yaml",
    source / "infra/compose/secure-search.host.override.yaml",
    source / "reports/runs/recovery_r01_search_tls_20261015/prepare_pki.py",
    source / "scripts/dev.py",
    source / ".github/workflows/ci.yml",
]
source_inputs = [{"path": str(path.relative_to(source)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
receipts = []
for path in sorted(directory.glob("*.json")):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(receipt, dict) and "start" in receipt and "exit_code" in receipt:
        receipts.append((path.name, receipt))
index = ["# Independent TLS review command index", "", "Every timestamp is Asia/Shanghai. Exact argv/cwd/raw output are in each JSON/log.", "", "| Receipt | Start | End | Exit | Test counts |", "|---|---|---|---|---|"]
for name, receipt in receipts:
    index.append(f"| {name} | {receipt.get('start')} | {receipt.get('end')} | {receipt.get('exit_code')} | {json.dumps(receipt.get('tests'), ensure_ascii=False)} |")
(directory / "command_index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
deliverables = [report, *sorted(path for path in directory.iterdir() if path.is_file() and path.suffix in {".py", ".md", ".json", ".xml", ".log"} and path.name != "artifact_manifest.json")]
manifest = {
    "start": started,
    "end": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "exit_code": 0 if not git_status.stdout else 1,
    "frozen_source_clean": not git_status.stdout,
    "source_inputs": source_inputs,
    "deliverables": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in deliverables],
    "excluded_generated_artifacts": [".coverage", "mypy_cache/", "pytest_cache_*/"],
}
(directory / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"frozen_source_clean": manifest["frozen_source_clean"], "deliverable_files": len(deliverables), "source_inputs": len(source_inputs), "start": manifest["start"], "end": manifest["end"]}))
