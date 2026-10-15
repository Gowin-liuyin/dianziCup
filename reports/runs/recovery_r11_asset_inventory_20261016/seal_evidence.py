"""新证据逐字节封存；保留首轮红日志，gzip可还原原始bytes/hash。"""

import gzip
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CODE_COMMIT = "6f82c68075dde808da9c92e3a49ad2e605e6b5a8"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    code = CODE_COMMIT
    config = json.loads(
        subprocess.check_output(
            [
                "wsl",
                "-d",
                "Ubuntu-22.04",
                "-u",
                "root",
                "--exec",
                "cat",
                "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
            ]
        )
    )
    secrets = [
        config[name].encode()
        for name in (
            "postgres_password",
            "redis_password",
            "TEST_DATABASE_URL",
            "TEST_REDIS_URL",
        )
        if config.get(name)
    ]
    source_proofs = []
    sources = [
        "backend/src/ai_intel/assets/inventory.py",
        "backend/src/ai_intel/assets/inventory_models.py",
        "backend/src/ai_intel/assets/inventory_contracts.py",
        "backend/src/ai_intel/assets/inventory_routes.py",
        "backend/tests/unit/test_r11_inventory.py",
        "backend/tests/contract/test_r11_inventory_contracts.py",
        "backend/tests/security/test_r11_inventory_boundary.py",
        "backend/tests/integration/test_t24_asset_inventory.py",
        "docs/decisions/CR-R11_asset_inventory.md",
    ]
    for path in sources:
        raw = subprocess.check_output(["git", "show", code + ":" + path], cwd=ROOT)
        frozen_object = subprocess.check_output(
            ["git", "rev-parse", code + ":" + path], cwd=ROOT, text=True
        ).strip()
        current_object = subprocess.check_output(
            ["git", "hash-object", path], cwd=ROOT, text=True
        ).strip()
        assert frozen_object == current_object
        source_proofs.append(
            {
                "path": path,
                "git_object": frozen_object,
                "git_blob_bytes": len(raw),
                "git_blob_sha256": digest(raw),
                "working_tree_filtered_matches": True,
            }
        )
    archives = []
    for path in sorted(RUN.rglob("*")):
        if (
            path.is_file()
            and path.name != "artifact_manifest.json"
            and path.suffix in {".log", ".xml", ".txt", ".json", ".py"}
        ):
            raw = path.read_bytes()
            if any(secret in raw for secret in secrets):
                raise RuntimeError("evidence contains a configured test credential")
            archive = Path(str(path) + ".gz")
            compressed = gzip.compress(raw, mtime=0)
            archive.write_bytes(compressed)
            assert gzip.decompress(compressed) == raw
            archives.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": len(raw),
                    "sha256": digest(raw),
                    "archive_path": archive.relative_to(ROOT).as_posix(),
                    "archive_bytes": len(compressed),
                    "archive_sha256": digest(compressed),
                }
            )
    results = {}
    for phase in (RUN, *sorted(path for path in RUN.iterdir() if path.is_dir())):
        for xml in phase.glob("*.xml"):
            tree = ET.parse(xml)
            cases = list(tree.iter("testcase"))
            results[xml.relative_to(RUN).as_posix()] = {
                "testcases": len(cases),
                "failures": sum(len(case.findall("failure")) for case in cases),
                "errors": sum(len(case.findall("error")) for case in cases),
                "skipped": sum(len(case.findall("skipped")) for case in cases),
                "seconds": sum(float(case.get("time", 0)) for case in cases),
            }
    artifacts = []
    for path in sorted(RUN.rglob("*")):
        if path.is_file() and path.suffix == ".gz":
            raw = path.read_bytes()
            if any(secret in raw for secret in secrets):
                raise RuntimeError("artifact contains a configured test credential")
            artifacts.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": len(raw),
                    "sha256": digest(raw),
                }
            )
    manifest = {
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "code_commit": code,
        "scope": "R11/T24 inventory persistence and independent router slice awaiting_review",
        "artifacts": artifacts,
        "raw_evidence_archives": archives,
        "source_proofs": source_proofs,
        "test_results": results,
        "secret_scan": {
            "configured_connection_secrets_found": 0,
            "scope": "new run artifacts and raw logs; matching allowed runtime configuration only",
        },
        "cbm_time_note": "CBM help/index/schema/trace command timestamps were not captured; raw command outputs preserved",
        "raw_note": "synthetic fixture logs only; real uploaded private bytes remain in PG and are not exported",
    }
    (RUN / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "code_commit": code,
                "artifacts": len(artifacts),
                "raw_archives": len(archives),
                "configured_secrets_found": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
