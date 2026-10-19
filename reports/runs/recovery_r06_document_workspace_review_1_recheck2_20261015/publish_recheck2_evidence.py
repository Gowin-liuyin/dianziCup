"""Copy only the recheck report and evidence, verifying exact bytes."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

workspace = Path("D:/wt/r06-doc-recheck2")
destination = Path("D:/dianzi")
report_relative = Path("reports/reviews/recovery/G-C-R06-document-workspace-review-1-recheck2.md")
run_relative = Path("reports/runs/recovery_r06_document_workspace_review_1_recheck2_20261015")
run_directory = workspace / run_relative
report_path = workspace / report_relative
authored_files = [report_path, *run_directory.glob("*.ts"), *run_directory.glob("*.mjs"), *run_directory.glob("*.py")]
violations = []
for path in authored_files:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line != line.rstrip(" \t"):
            violations.append({"path": path.relative_to(workspace).as_posix(), "line": number})
if violations:
    raise RuntimeError(f"Authored trailing whitespace: {violations}")
files = [report_path, *(path for path in run_directory.rglob("*") if path.is_file() and path.name not in {"delivery_manifest.json", "delivery_receipt.json"})]
entries = [{"path": path.relative_to(workspace).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(files)]
manifest = {"recorded_at": datetime.now().astimezone().isoformat(), "source": str(workspace), "destination": str(destination), "authored_trailing_whitespace": violations, "excluded_self_files": ["delivery_manifest.json", "delivery_receipt.json"], "files": entries}
(run_directory / "delivery_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for relative in [report_relative, run_relative]:
    target = (destination / relative).resolve()
    if not target.is_relative_to(destination.resolve()) or target.exists():
        raise RuntimeError(f"Refusing unsafe or existing delivery target: {target}")
(destination / report_relative).parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(report_path, destination / report_relative)
shutil.copytree(run_directory, destination / run_relative)
differences = [entry["path"] for entry in entries if hashlib.sha256((destination / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]]
receipt = {"recorded_at": datetime.now().astimezone().isoformat(), "files_verified": len(entries), "copy_hash_differences": differences, "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(), "manifest_sha256": hashlib.sha256((run_directory / "delivery_manifest.json").read_bytes()).hexdigest()}
for directory in [run_directory, destination / run_relative]:
    (directory / "delivery_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if differences:
    raise RuntimeError(f"Delivery byte mismatch: {differences}")
print(json.dumps(receipt, ensure_ascii=False))
