"""Seal and verify original bytes without a self-referential manifest hash."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CODE_SHA = "dd36cf78c3d15138683d09c12ea867c0055b9674"
REPORT = ROOT / "reports/tasks/R09-shared-timeout-combination.md"
MANIFEST = RUN / "artifact_manifest.json"
SIDECAR = RUN / "artifact_manifest.sha256"
EXCLUDED = ("artifact_manifest.json", "artifact_manifest.sha256")


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def material_files() -> list[Path]:
    """Exclude only the manifest cycle and the seal/verify command receipts."""
    files = [ROOT / ".gitattributes", REPORT]
    for path in sorted(RUN.iterdir()):
        is_freeze_receipt = path.name.startswith("freeze_") and path.suffix in {
            ".json",
            ".log",
            ".sha256",
        }
        if path.is_file() and path.name not in EXCLUDED and not is_freeze_receipt:
            files.append(path)
    return files


def main() -> None:
    """Hash actual bytes, then verify both the body and every listed file."""
    if sys.argv[1] == "seal":
        records = []
        for path in material_files():
            content = path.read_bytes()
            records.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "size_bytes": len(content),
                    "sha256": digest(content),
                }
            )
        manifest = {
            "schema_version": 1,
            "sealed_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "base_sha": "ed217564e9cf3571b430d0fe7caa4d3999c7320b",
            "combination_code_sha": CODE_SHA,
            "combination_code_tree": subprocess.check_output(
                ["git", "rev-parse", f"{CODE_SHA}^{{tree}}"], cwd=ROOT, text=True
            ).strip(),
            "status": "awaiting_review",
            "scope": "R09 public-card preparation plus shared timeout fix; no R09 acceptance",
            "excluded": [*EXCLUDED, "freeze_* receipts and prior seals (avoid hash cycles)"],
            "files": records,
        }
        body = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        MANIFEST.write_bytes(body)
        SIDECAR.write_bytes((digest(body) + "  artifact_manifest.json\n").encode())
    elif sys.argv[1] != "verify":
        raise ValueError("expected seal or verify")
    body = MANIFEST.read_bytes()
    assert digest(body) == SIDECAR.read_text(encoding="utf-8").split()[0]
    manifest = json.loads(body)
    assert {item["path"] for item in manifest["files"]} == {
        path.relative_to(ROOT).as_posix() for path in material_files()
    }
    for item in manifest["files"]:
        content = (ROOT / item["path"]).read_bytes()
        assert len(content) == item["size_bytes"]
        assert digest(content) == item["sha256"], item["path"]
    print(
        json.dumps(
            {"manifest_sha256": digest(body), "files": len(manifest["files"]), "verified": True},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
