"""Keep the first uncommitted manifest and fix only diagnostic byte-preservation rules."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == "71e594cb958bd93d21fb7ed66574b3cba4cc47e1"
at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
with (RUN / "author_material_v1_diff_check.log").open("xb") as output:
    result = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
assert result.returncode == 2
prior = RUN / "artifact_manifest.json"
old = json.loads(prior.read_text(encoding="utf-8"))
for name in ("artifact_manifest.json", "artifact_manifest.sha256"):
    source = RUN / name
    target = RUN / name.replace("artifact_manifest", "artifact_manifest_v1_uncommitted")
    assert source.resolve().parent == RUN.resolve() and target.resolve().parent == RUN.resolve() and not target.exists()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    source.rename(target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before
attributes = ROOT / ".gitattributes"
content = attributes.read_text(encoding="utf-8")
content = content.replace("reports/tasks/R07-enrichment-publication.md -text\n", "reports/tasks/R07-enrichment-publication.md -text whitespace=trailing-space,space-before-tab,cr-at-eol\n")
line = "reports/runs/recovery_r07_publication_20261015/roster_guard_staged.diff -diff"
if line not in content.splitlines():
    content += line + "\n"
attributes.write_text(content, encoding="utf-8")
issue = {"at": at, "prior_uncommitted_manifest_sha256": hashlib.sha256((RUN / "artifact_manifest_v1_uncommitted.json").read_bytes()).hexdigest(), "first_failure": "cached diff-check exit2: CRLF author report lacked cr-at-eol; raw staged diff contains original patch blank-context lines", "business_source_changed": False, "raw_logs_transcoded": False, "fix": "one task report cr-at-eol rule, one exact raw diagnostic diff -diff; other log/xml rules remain scoped to this run", "prior_manifest_was_committed": False}
(RUN / "author_material_attribute_repair.json").write_text(json.dumps(issue, indent=2) + "\n", encoding="utf-8")
members = [ROOT / "reports/tasks/R07-enrichment-publication.md"] + sorted(path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
entries = [{"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in members]
old["files"], old["sealed_at"] = entries, at
old["raw_transcoding"] = "none; original failed metadata attempt retained as v1_uncommitted"
prior.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
digest = hashlib.sha256(prior.read_bytes()).hexdigest()
sidecar = RUN / "artifact_manifest.sha256"
sidecar.write_text(digest + "  artifact_manifest.json\n", encoding="utf-8")
paths = [entry["path"] for entry in entries] + [prior.relative_to(ROOT).as_posix(), sidecar.relative_to(ROOT).as_posix(), ".gitattributes"]
subprocess.run(["git", "add", "--", *paths], cwd=ROOT, check=True)
for entry in entries + [{"path": prior.relative_to(ROOT).as_posix(), "sha256": digest}]:
    assert hashlib.sha256(subprocess.check_output(["git", "show", ":" + entry["path"]], cwd=ROOT)).hexdigest() == entry["sha256"], entry["path"]
with (RUN / "author_material_v2_diff_check.log").open("xb") as output:
    check = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
assert check.returncode == 0
with (RUN / "author_material_commit.log").open("xb") as output:
    subprocess.run(["git", "commit", "-m", "G-C R07 preserve author candidate evidence and unresolved review failures"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
receipt = {"at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": old["code_sha"], "material_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "manifest_sha256": digest, "manifest_members": len(entries), "raw_blob_mismatches": 0, "accepted": False, "post_seal_supplements": ["author_material_v2_diff_check.log", "author_material_commit.log"]}
(RUN / "author_material_commit_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
