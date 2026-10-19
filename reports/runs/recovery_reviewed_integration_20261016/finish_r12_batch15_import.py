"""Resume scoped evidence copying without replacing conflicting local files."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SCOPES = (
    "reports/tasks/R12-projection-failure-budget.md",
    "reports/reviews/recovery/G-D-R12-projection-failure-budget-review-1.md",
    "reports/runs/r12_projection_failure_budget_20261017/",
    "reports/runs/r12_projection_failure_budget_review1_20261017/",
)


def main() -> None:
    imports = json.loads((RUN / "r12_scoped_archives.json").read_text(encoding="utf-8"))
    verified = []
    for item in imports:
        archive = Path(item["archive"])
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError("scoped_archive_hash_mismatch")
        with ZipFile(archive) as source:
            for member in source.infolist():
                if member.is_dir():
                    continue
                name = member.filename
                if not any(name == scope or name.startswith(scope) for scope in SCOPES):
                    raise RuntimeError("evidence_scope_mismatch")
                target = (ROOT / name).resolve()
                if not target.is_relative_to(ROOT.resolve()):
                    raise RuntimeError("evidence_target_outside_workspace")
                content = source.read(member)
                existed = target.exists()
                conflicting_existing = existed and target.read_bytes() != content
                if conflicting_existing:
                    target = RUN / "incoming" / ("r12_" + item["ref"][:8]) / name
                    existed = target.exists()
                    if existed and target.read_bytes() != content:
                        raise RuntimeError("protected_incoming_evidence_conflict:" + name)
                if not existed:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                verified.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(),
                                 "preexisting_equal": existed, "source": item["ref"],
                                 "stored_path": str(target.relative_to(ROOT)),
                                 "conflicting_existing_preserved": conflicting_existing})
    receipt = RUN / "reviewed_r12_batch15_import.json"
    if receipt.exists():
        raise RuntimeError("refusing_import_receipt_overwrite")
    receipt.write_text(json.dumps({
        "recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "source_sha": "9cd6381eacc67853c055643d634ffb1812875214",
        "interrupted_initial_copy": "receipt_absent;three_source_files_reverified_exact",
        "evidence": verified,
        "root_integration_tests": "not_run",
        "integration": "not_run", "live": "not_run", "manual": "not_run",
    }, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verified_evidence_files": len(verified), "receipt": str(receipt)}))


if __name__ == "__main__":
    main()
