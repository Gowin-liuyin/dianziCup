"""Resolve only reviewed CVSS semantics and resume the failed immutable merge record."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
TARGET = "9e722c944cf83086ffd30ad24a708172c13da189"
BEFORE = "136fbaef337036d95229aa4976c1ba49b2e6b04c"
SOURCE_PATHS = (
    "backend/src/ai_intel/enrichment/signals.py",
    "backend/tests/unit/test_r07_public_signals.py",
    "backend/tests/unit/test_r07_public_signals_fix1.py",
)


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, encoding="utf-8").strip()


def blob(revision, path):
    return subprocess.check_output(["git", "show", revision + ":" + path], cwd=ROOT)


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


assert git("rev-parse", "HEAD") == BEFORE
assert git("rev-parse", "MERGE_HEAD") == TARGET
assert sorted(git("diff", "--name-only", "--diff-filter=U").splitlines()) == sorted((".gitattributes", *SOURCE_PATHS))
path = RUN / "persistent_slices_integration_receipt.json"
receipt = json.loads(path.read_text(encoding="utf-8"))
item = receipt["packages"][0]
assert item["target_material_sha"] == TARGET
resolved = []
for source in SOURCE_PATHS:
    ours, theirs = blob(":2", source), blob(":3", source)
    assert ours == blob(BEFORE, source) and theirs == blob(TARGET, source)
    (ROOT / source).write_bytes(theirs)
    resolved.append({"path": source, "before_sha256": hashlib.sha256(ours).hexdigest(), "after_sha256": hashlib.sha256(theirs).hexdigest(), "resolution": "exact independently reviewed 2ba/dc04 source; CVSS authority included in conflict scope and matching regression fixtures; original red evidence preserved"})
base, ours, theirs = [blob(":" + str(stage), ".gitattributes").decode().splitlines() for stage in (1, 2, 3)]
assert set(base) <= set(ours) and set(base) <= set(theirs)
additions = [line for line in theirs if line not in ours]
assert all(not line or line.startswith("reports/") for line in additions)
(ROOT / ".gitattributes").write_text("\n".join(ours + additions) + "\n", encoding="utf-8")
subprocess.run(["git", "add", "--", ".gitattributes", *SOURCE_PATHS], cwd=ROOT, check=True)
assert not git("diff", "--name-only", "--diff-filter=U")
with (RUN / "publication-provenance_semantic_resolution.log").open("xb") as output:
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
    subprocess.run(["git", "commit", "-m", "G-C integrate reviewed atomic enrichment publication and CVSS authority scope"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
item["semantic_conflict_resolution"] = {"resolved_at": now(), "files": resolved, "attribute_additions": additions}
item["final_head"] = git("rev-parse", "HEAD")
receipt["ended_at"] = now()
path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"publication_head": item["final_head"], "resolved_source_files": len(resolved), "push_attempts": 0}))
