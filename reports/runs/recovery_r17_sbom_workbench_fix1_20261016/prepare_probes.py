"""Preserve frozen evidence and adapt only the independent test resource origin for red reproduction."""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
AUTHOR = Path("D:/wt/r17-sbom-workbench")
REVIEW = Path("D:/wt/r17-sbom-review1")
REVIEW_RUN = REVIEW / "reports/runs/recovery_r17_sbom_workbench_review1_20261016"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


proof = []
for directory, relative, expected, count in (
    (AUTHOR, "reports/runs/recovery_r17_sbom_workbench_20261016/raw_manifest.json", "d999188d6d884ce4dd25cb51c0aad5f1ce2478654e1a0e8adae109ac18c9b03d", 118),
    (REVIEW, "reports/runs/recovery_r17_sbom_workbench_review1_20261016/raw_manifest.json", "d7f22390774e910a685c6db24d66beb2b63176e24b31fae7c4f7e09e7731aeb7", 272),
):
    path = directory / relative
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise RuntimeError("frozen prior manifest changed")
    manifest = json.loads(raw)
    if len(manifest["members"]) != count:
        raise RuntimeError("unexpected prior evidence denominator")
    rows = []
    for member in manifest["members"]:
        frozen = (directory / member["path"]).read_bytes()
        if digest(frozen) != member["sha256"] or len(frozen) != member["bytes"]:
            raise RuntimeError("prior raw evidence drifted")
        rows.append({"path": member["path"], "sha256": digest(frozen), "bytes": len(frozen)})
    proof.append({"root": str(directory), "manifest_sha256": expected, "members": rows, "mismatches": 0})
(RUN / "prior_evidence_before.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8", newline="\n")
original = (REVIEW_RUN / "independent.spec.ts").read_bytes()
(RUN / "reviewer_original.spec.ts.txt").write_bytes(original)
adapted = original.decode("utf-8").replace("26173", "26373")
(RUN / "reviewer_resource_adapter.spec.ts").write_text(adapted, encoding="utf-8", newline="\n")
(RUN / "package.json").write_text('{"type":"module"}\n', encoding="utf-8", newline="\n")
prefix = adapted.split("const unsafeUris = [", 1)[0]
(RUN / "reviewer_fixture.ts").write_text(prefix.replace("async function fixture(", "export async function fixture(").replace("async function clearAssertion(", "export async function clearAssertion("), encoding="utf-8", newline="\n")
for name in ("backend_dto_probe.ts", "backend_purl_profile.py"):
    (RUN / (name + ".original.txt")).write_bytes((REVIEW_RUN / name).read_bytes())
receipt = {"prepared_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
           "reviewer_original_spec_sha256": digest(original), "resource_adapter_only_change": "26173 → 26373",
           "original_assertions_unchanged": adapted.replace("26373", "26173") == original.decode("utf-8"),
           "fixture_prefix_reuse": "identical prefix plus exports and resource origin, no product edits",
           "prior_author_members": 118, "prior_review_members": 272, "prior_raw_mismatches": 0}
(RUN / "probe_prepare_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
