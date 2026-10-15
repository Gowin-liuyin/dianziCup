"""Retain the first sealing failure and recognize CRLF only for this exact report."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
report = ROOT / "reports/tasks/R07-publication-combined-fix.md"
manifest = RUN / "artifact_manifest.json"
first = json.loads(manifest.read_text())
assert first["code_sha"] == "dc04d193185324f6913cde8efc40f4b238047dd8"
for original, archived in (
    (manifest, RUN / "artifact_manifest_v1_uncommitted.json"),
    (RUN / "artifact_manifest.sha256", RUN / "artifact_manifest_v1_uncommitted.sha256"),
    (report, RUN / "report_v1_uncommitted.md"),
):
    with archived.open("xb") as output:
        output.write(original.read_bytes())
red = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, capture_output=True)
assert red.returncode == 2
(RUN / "material_v1_diff_check_failure.log").write_bytes(red.stdout + red.stderr)
at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
attributes = ROOT / ".gitattributes"
content = attributes.read_text()
content = content.replace(
    "reports/tasks/R07-publication-combined-fix.md -text\n",
    "reports/tasks/R07-publication-combined-fix.md -text whitespace=cr-at-eol\n",
)
attributes.write_text(content, encoding="utf-8")
body = report.read_text()
body += f"\n{at} /root修订：材料首次封存git diff --cached --check exit2，Windows报告原CRLF在-text保真后被默认diff判尾随空白；仅本报告路径追加whitespace=cr-at-eol，raw bytes不转写。v1 uncommitted manifest/报告副本和红diff保留；源/test未改，该问题不计业务失败。\n"
body = "\n".join(
    prefix + at if line.startswith(prefix) else line
    for line in body.splitlines()
    for prefix in ["最后更新时间："]
) + "\n"
report.write_text(body, encoding="utf-8")
paths = sorted(path for path in [report, *RUN.glob("*")] if path.is_file() and path.name not in {"artifact_manifest.json", "artifact_manifest.sha256"})
rows = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
first["artifacts"], first["sealed_at"] = rows, at
first["material_revision"] = 2
first["v1_historical_report_mapping"] = {
    "original_path": "reports/tasks/R07-publication-combined-fix.md",
    "preserved_copy": (RUN / "report_v1_uncommitted.md").relative_to(ROOT).as_posix(),
    "status": "v1 manifest was never committed; current report intentionally revised with timestamp",
}
manifest.write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
(RUN / "artifact_manifest.sha256").write_text(manifest_hash + "\n", encoding="ascii")
selected = [".gitattributes", *[row["path"] for row in rows], manifest.relative_to(ROOT).as_posix(), (RUN / "artifact_manifest.sha256").relative_to(ROOT).as_posix()]
subprocess.run(["git", "add", "--", *selected], cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
for row in rows:
    blob = subprocess.check_output(["git", "show", ":" + row["path"]], cwd=ROOT)
    assert hashlib.sha256(blob).hexdigest() == row["sha256"], row["path"]
subprocess.run(["git", "commit", "-m", "R07 seal publication repair combination with exact raw evidence"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
print(json.dumps({"material_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "code_sha": first["code_sha"], "manifest_sha256": manifest_hash, "artifacts": len(rows), "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "raw_blob_verified": True, "pushes": 0}))
