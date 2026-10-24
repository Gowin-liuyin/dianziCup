"""Generate the R20 registry extension artifacts for the 54 recorded classifications.

Reads the batch20 classification records (whose first 136 entries must equal the
live registry), derives proposal-row provenance fields (line, match_sha256,
value_sha256) from the current file bytes using the exact conventions of the
reviewed R20 proposal, builds a stored-format fixture bundle, and rewrites the
live classification table with the 54 appended records. Refuses to run when the
table has already been extended. Run from the repository root.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_RECORDS = (
    ROOT
    / "reports/runs/batch20_secret_classification_20261024/classification_records_54_ready_to_land.json"
)
TABLE = ROOT / "reports/security/recovery_fixture_false_positives.json"
BUNDLE = ROOT / "fixtures/synthetic/security/r20_registry_extension_batch21.zip"
PROPOSAL = Path(__file__).resolve().parent / "registration_proposal.json"
PRIOR_PROPOSAL = ROOT / "reports/runs/recovery_r20_secret_provenance_20261016/registration_proposal.json"
REASON = "recorded_synthetic_evidence_with_provenance_chain"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def git_blob_sha(content: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(f"blob {len(content)}\0".encode())
    digest.update(content)
    return digest.hexdigest()


def normalized_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")


def main() -> int:
    table_bytes = TABLE.read_bytes()
    table = json.loads(table_bytes.decode("utf-8"))
    if len(table["records"]) != 136:
        print(f"ERROR live table has {len(table['records'])} records, expected 136", file=sys.stderr)
        return 2

    source = json.loads(SOURCE_RECORDS.read_text(encoding="utf-8"))
    records = source["records"]
    if records[:136] != table["records"]:
        print("ERROR first 136 source records no longer match the live table", file=sys.stderr)
        return 2
    new_records = records[136:]
    if len(new_records) != 54:
        print(f"ERROR source tail has {len(new_records)} records, expected 54", file=sys.stderr)
        return 2

    paths = sorted({record["path"] for record in new_records})
    bindings: dict[str, dict[str, str]] = {}
    for path in paths:
        raw = (ROOT / path).read_bytes()
        bindings[path] = {
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=ROOT
            ).stdout.strip(),
            "source_path": path,
            "source_blob": git_blob_sha(raw),
            "raw_sha256": sha256_bytes(raw),
        }

    proposals = []
    for record in new_records:
        raw = (ROOT / record["path"]).read_bytes()
        if sha256_bytes(raw) != record["raw_sha256"]:
            print(f"ERROR current bytes of {record['path']} no longer match the record", file=sys.stderr)
            return 2
        content = normalized_text(raw)
        matched = content[record["start"] : record["end"]]
        quote = min(index for index, char in enumerate(matched) if char in "\"'")
        if matched[-1] != matched[quote]:
            print(f"ERROR unmatched quote frame in {record['path']} at {record['start']}", file=sys.stderr)
            return 2
        value = matched[quote + 1 : -1]
        proposals.append(
            {
                "path": record["path"],
                "line": content[: record["start"]].count("\n") + 1,
                "pattern_id": record["pattern_id"],
                "start": record["start"],
                "end": record["end"],
                "raw_sha256": record["raw_sha256"],
                "match_sha256": sha256_bytes(matched.encode()),
                "value_sha256": sha256_bytes(value.encode()),
                "reason": REASON,
                "fixture_origin": record["fixture_origin"],
                "review_ref": record["review_ref"],
                "review_status": "awaiting_independent_review",
                "raw_variant": "original_physical",
            }
        )

    with zipfile.ZipFile(BUNDLE, "w", compression=zipfile.ZIP_STORED) as archive:
        written_digests: set[str] = set()
        for path in paths:
            digest = bindings[path]["raw_sha256"]
            if digest in written_digests:
                continue
            written_digests.add(digest)
            entry = zipfile.ZipInfo(f"{digest}.bin", date_time=(1980, 1, 1, 0, 0, 0))
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, (ROOT / path).read_bytes())

    baseline = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=ROOT
    ).stdout.strip()
    proposal_document = {
        "prepared_at": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
        "baseline_sha": baseline,
        "prior_proposal": PRIOR_PROPOSAL.relative_to(ROOT).as_posix(),
        "prior_proposal_sha256": sha256_bytes(PRIOR_PROPOSAL.read_bytes()),
        "source_records": SOURCE_RECORDS.relative_to(ROOT).as_posix(),
        "source_records_sha256": sha256_bytes(SOURCE_RECORDS.read_bytes()),
        "old_records_unchanged": True,
        "new_records": len(new_records),
        "total_records": len(table["records"]) + len(new_records),
        "review_status": "awaiting_independent_review",
        "proposals": proposals,
        "fixture_bindings": bindings,
        "fixture_bundle": {
            "path": BUNDLE.relative_to(ROOT).as_posix(),
            "raw_sha256": sha256_bytes(BUNDLE.read_bytes()),
            "data_mode": "fixture",
            "format": "zip_stored",
            "zip_entry_timestamp": "format_default_1980_not_run_time",
        },
        "table_records": new_records,
    }
    PROPOSAL.write_text(json.dumps(proposal_document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    extended = dict(table)
    extended["records"] = table["records"] + new_records
    TABLE.write_text(json.dumps(extended, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    sys.path.insert(0, str(ROOT / "scripts"))
    from security_scan import load_fixture_classifications

    parsed = load_fixture_classifications(ROOT, TABLE)
    print(f"extension_written proposal={len(proposals)} table_records={len(extended['records'])} loader_parsed={len(parsed)}")
    print(f"bundle_sha256={proposal_document['fixture_bundle']['raw_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
