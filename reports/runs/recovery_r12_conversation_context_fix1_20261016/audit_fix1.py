"""Audit frozen input bytes, Git blobs and bounded output; never capture a secret value."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
AUTHOR = Path("D:/wt/r12-conversation-context")
AUTHOR_RUN = AUTHOR / "reports/runs/recovery_r12_conversation_context_20261016"
REVIEW = Path("D:/wt/r12-conversation-context-review1")
REVIEW_RUN = REVIEW / "reports/runs/recovery_r12_conversation_context_review1_20261016"
SOURCE_FILES = [
    "backend/src/ai_intel/answering/conversation_context.py",
    "backend/src/ai_intel/answering/conversation_contracts.py",
    "backend/src/ai_intel/answering/conversation_models.py",
    "backend/src/ai_intel/answering/evidence_bundle.py",
    "backend/tests/unit/test_r12_conversation_boundary_fix1.py",
    "backend/tests/integration/test_r12_conversation_boundary_fix1_pg.py",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blob(path, directory=ROOT):
    return subprocess.check_output(
        ["git", "hash-object", "--path=" + path, str(directory / path)], cwd=directory
    ).decode().strip()


def save(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def audit():
    checked = []
    for name in ("material_manifest.json", "caller_source_manifest.json", "implementation_source_manifest.json"):
        entries = json.loads((AUTHOR_RUN / name).read_text(encoding="utf-8"))
        checks = []
        for entry in entries:
            original = (AUTHOR_RUN if name == "material_manifest.json" else AUTHOR) / entry["path"]
            checkout = (ROOT / "reports/runs/recovery_r12_conversation_context_20261016" if name == "material_manifest.json" else ROOT) / entry["path"]
            checks.append(dict(
                path=entry["path"], author_original_raw_match=digest(original) == entry["sha256"],
                fix_checkout_raw_match=digest(checkout) == entry["sha256"],
                fix_checkout_raw_sha256=digest(checkout),
                fix_change_authorized=entry["path"] in SOURCE_FILES,
                checkout_blob=None if name == "material_manifest.json" else blob(entry["path"]),
                clean_filter_match=None if name == "material_manifest.json" else blob(entry["path"]) == entry["clean_filter_blob"],
            ))
        assert all(item["author_original_raw_match"] for item in checks)
        if name == "material_manifest.json":
            assert all(item["fix_checkout_raw_match"] for item in checks)
        if name in {"implementation_source_manifest.json", "caller_source_manifest.json"}:
            assert all(item["clean_filter_match"] or item["fix_change_authorized"] for item in checks)
        checked.append(dict(manifest=name, count=len(entries), checks=checks))
    same7 = RUN / "test_review_negative.py"
    assert digest(same7) == "9e813862bbf5def30138a7ea67ae140a4ad5c599c6362f142f91f88d8401e9d7"
    assert same7.read_bytes() == (REVIEW_RUN / same7.name).read_bytes()
    assert (RUN / "test_review_boundaries.py").read_bytes() == (REVIEW_RUN / "test_review_boundaries.py").read_bytes()
    save("source_protection.json", dict(
        checked_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        author_code="6259db6d98d67c1be274370ce20775133a8b0520",
        author_material="f557df069a0e0eb74194557ebdb9be338d9a5b0e",
        reviewer_material="6383926b169e7f9ac657e9a32a5802f116937d25",
        checked=checked, same7_sha256=digest(same7),
        same7_original_blob="e4214bb50966ce53ef8fb9d34899d4225a14eb05",
    ))
    save("fix1_source_manifest.json", [
        dict(path=path, sha256=digest(ROOT / path), clean_filter_blob=blob(path))
        for path in SOURCE_FILES
    ])
    sys.path.insert(0, str(ROOT / "backend/src"))
    from ai_intel.answering.conversation_models import IMMUTABILITY_FUNCTION_DDL, IMMUTABILITY_TRIGGER_DDL
    approved = json.loads(Path("D:/wt/r07-r12-r10-r18-migrations/reports/runs/recovery_forward_migrations_0023_0026_20261016/approved_guards.json").read_text())
    matches = []
    for statement in (IMMUTABILITY_FUNCTION_DDL, IMMUTABILITY_TRIGGER_DDL):
        actual = hashlib.sha256(statement.strip().encode()).hexdigest()
        expected = next(item["sha256_utf8"] for item in approved if item["statement"] == statement.strip())
        assert actual == expected
        matches.append(dict(statement=statement.strip(), sha256_utf8=actual))
    save("metadata_0024_guard_match.json", matches)
    print(json.dumps(dict(author_manifest_counts=[item["count"] for item in checked], same7_original_bytes=True)))


def seal():
    report = ROOT / "reports/tasks/R12-conversation-context-fix1.md"
    excluded = {"material_manifest.json", "material_manifest.sha256", "freeze_receipt.json"}
    paths = [path for path in RUN.iterdir() if path.is_file() and path.name not in excluded]
    paths.append(report)
    entries = [dict(path=str(path.relative_to(ROOT)).replace("\\", "/"), sha256=digest(path),
                    clean_filter_blob=blob(str(path.relative_to(ROOT)).replace("\\", "/")))
               for path in sorted(paths)]
    save("material_manifest.json", entries)
    manifest = RUN / "material_manifest.json"
    (RUN / "material_manifest.sha256").write_text(digest(manifest) + "\n", encoding="ascii")
    save("freeze_receipt.json", dict(
        checked_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        code_commit="1e210090d74d1444101330f0c8b8637ad1dd50a3",
        material_parent_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        report_sha256=digest(report), manifest_sha256=digest(manifest),
        material_count=len(entries), self_reference_exclusions=sorted(excluded),
        status="awaiting_review", push="not_run", final_acceptance="not_run",
    ))
    print(json.dumps(dict(material_count=len(entries), manifest_sha256=digest(manifest))))


if __name__ == "__main__":
    if sys.argv[1] == "audit":
        audit()
    else:
        seal()
