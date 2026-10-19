"""Seal raw review materials and scan actual authorized credentials without printing them."""

import hashlib
import json
import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url

from review_runner import CODE, MATERIALS, ROOT, RUN, SECRET_SOURCE, stamp


def main() -> None:
    report = ROOT / "reports/reviews/recovery/G-D-R12-hybrid-retrieval-review-1.md"
    captured = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", SECRET_SOURCE], capture_output=True, check=True, timeout=15)
    connection = json.loads(captured.stdout)
    password = make_url(connection["TEST_DATABASE_URL"]).password or ""
    credentials = [connection["TEST_DATABASE_URL"], password]
    credentials.extend(value for name, value in connection.items() if "PASSWORD" in name and isinstance(value, str))
    entries = []
    excluded = {"review_manifest.json", "seal_receipt.json", "seal.log", "seal.command.json"}
    paths = sorted(path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.name not in excluded)
    for path in [report, *paths]:
        raw = path.read_bytes()
        assert all(not credential or credential.encode() not in raw for credential in credentials), "credential_found"
        entries.append(dict(path=path.relative_to(ROOT).as_posix(), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    receipt = dict(sealed_at=stamp(), code_sha=CODE, materials_sha=MATERIALS, report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(), credential_findings=0, entries=entries, excluded="self manifest/receipt/seal command log, Python caches", business_files="unchanged")
    (RUN / "review_manifest.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = dict(sealed_at=receipt["sealed_at"], report_sha256=receipt["report_sha256"], manifest_sha256=hashlib.sha256((RUN / "review_manifest.json").read_bytes()).hexdigest(), material_count=len(entries), credential_findings=0, status="sealed")
    (RUN / "seal_receipt.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
