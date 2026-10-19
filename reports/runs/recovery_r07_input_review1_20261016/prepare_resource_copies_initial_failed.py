"""Copy original PG tests while changing only review-owned resource guards and CAS paths."""

import difflib
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
DESTINATION = RUN / "resource_copies"
SOURCE_SHA = "7aeb85ae8277c048fb762dbc705436602cb18f9d"
NAMES = (
    "test_r10_evidence_graph_pg.py",
    "test_r10_graph_validity_pg.py",
    "test_r10_graph_source_coverage_pg.py",
    "test_r10_graph_fix2_pg.py",
    "test_r07_enrichment_publication_pg.py",
    "test_r07_publication_rule_provenance_pg.py",
    "test_r07_publication_acl_lock_fix_pg.py",
    "test_r06_catalog_documents_pg.py",
)
DESTINATION.mkdir(exist_ok=True)
records = []
all_diff = []
for name in NAMES:
    relative = "backend/tests/integration/" + name
    original = subprocess.check_output(["git", "show", SOURCE_SHA + ":" + relative], cwd=ROOT)
    changed = original
    replacements = []
    if name == "test_r10_evidence_graph_pg.py":
        replacements = [
            (b'assert url.database == "test_dianzi_r06_catalog_r10_graph_20261016"', b'assert url.database.startswith("test_dianzi_r07_input_review1_")'),
            (b'assert url.database.startswith("test_dianzi_r06_catalog_")', b'assert url.database.startswith("test_dianzi_r07_input_review1_")'),
            (b'FIXTURE_RAW_DIRECTORY = Path(tempfile.gettempdir()) / "dianzi-r10-graph-fixture-raw"', b'FIXTURE_RAW_DIRECTORY = Path(__file__).resolve().parents[1] / "owned_r10_fixture_cas"'),
        ]
    elif name == "test_r06_catalog_documents_pg.py":
        replacements = [(b'assert url.database.startswith("test_dianzi_r06_catalog_")', b'assert url.database.startswith("test_dianzi_r07_input_review1_")')]
    for before, after in replacements:
        assert changed.count(before) == 1
        changed = changed.replace(before, after)
    reverted = changed
    for before, after in reversed(replacements):
        reverted = reverted.replace(after, before, 1)
    assert reverted == original
    assert b'assert url.database.startswith("test_dianzi_r06_catalog_")' not in changed
    (DESTINATION / name).write_bytes(changed)
    snapshot = RUN / "original_resource_test_blobs" / name
    snapshot.parent.mkdir(exist_ok=True)
    snapshot.write_bytes(original)
    diff = "".join(difflib.unified_diff(original.decode().splitlines(keepends=True), changed.decode().splitlines(keepends=True), fromfile=relative, tofile=str(DESTINATION / name)))
    all_diff.append(diff)
    records.append({"source_sha": SOURCE_SHA, "original_path": relative, "copy_path": str((DESTINATION / name).relative_to(ROOT)).replace("\\", "/"), "original_git_bytes_sha256": hashlib.sha256(original).hexdigest(), "copy_raw_sha256": hashlib.sha256(changed).hexdigest(), "resource_only_replacements": len(replacements), "exact_business_bytes_preserved_after_reverting_guard_replacements": True})
(RUN / "resource_copy_diff.patch").write_text("".join(all_diff), encoding="utf-8")
receipt = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "authorized_by": "/root 2026-10-16 final resource instruction", "source_sha": SOURCE_SHA, "files": records, "changed_business_assertions": 0, "original_tests_written": False, "shared_cas_written": False}
(RUN / "resource_copy_manifest.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_sha": SOURCE_SHA, "files": len(records), "resource_replacements": sum(item["resource_only_replacements"] for item in records), "changed_business_assertions": 0}))
