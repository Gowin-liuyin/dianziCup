"""Verify frozen author/reviewer materials and the exact unchanged review probe."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent


if __name__ == "__main__":
    protected = []
    for root, relative_manifest, expected in (
        (
            Path("D:/wt/r18-client-sdk"),
            "reports/runs/recovery_r18_client_sdk_20261016/artifact_manifest.json",
            "c381854c08a66ccf0f5e22644e3e852e7aa3a17cd4a1ab1eaeccf9663089e6fb",
        ),
        (
            Path("D:/wt/r18-sdk-client-review1"),
            "reports/runs/recovery_r18_sdk_cli_review1_20261016/artifact_manifest.json",
            "03ff1575004f98269b25397653b54930096e21d57146681d7ee8b42c31faa687",
        ),
    ):
        original = root / relative_manifest
        raw = original.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        manifest = json.loads(raw)
        for entry in manifest["artifacts"]:
            assert (
                hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest()
                == entry["raw_sha256"]
            ), entry["path"]
        protected.append(
            {
                "root": str(root),
                "manifest_sha256": expected,
                "member_count": len(manifest["artifacts"]),
                "all_raw_member_hashes_unchanged": True,
            }
        )
    upstream = Path(
        "D:/wt/r18-sdk-client-review1/reports/runs/"
        "recovery_r18_sdk_cli_review1_20261016/test_independent_boundaries.py"
    ).read_bytes()
    copied = (RUN / "test_independent_boundaries.py").read_bytes()
    assert copied == upstream
    report = Path(
        "D:/wt/r18-sdk-client-review1/reports/reviews/recovery/G-E-R18-sdk-cli-review-1.md"
    )
    report_hash = hashlib.sha256(report.read_bytes()).hexdigest()
    assert report_hash == "b3d9c3cfe11ac84e6f1b39db6c025309b016fed67f40ea7676cf663d06b70527"
    receipt = {
        "observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "protected": protected,
        "review_report_sha256": report_hash,
        "copied_probe_sha256": hashlib.sha256(copied).hexdigest(),
        "copied_probe_exact_bytes_unchanged": True,
    }
    target = RUN / "protected_upstream.json"
    assert not target.exists()
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))
