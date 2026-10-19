"""Seal raw and Git-filtered material bytes after an in-memory exact credential scan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
SOURCE_COMMIT = "8e0485231bf9367d5b4b3a79802bdf346b1fb745"
SOURCE_PATHS = (
    "backend/src/ai_intel/api/credentials.py",
    "backend/tests/unit/test_r18_api_key_post_lock_time.py",
    "backend/tests/integration/test_r18_api_key_post_lock_time_pg.py",
)
REPORT_PATH = "reports/tasks/R18-api-key-expiry-fix2.md"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_record(path: Path) -> dict[str, str]:
    relative = path.relative_to(ROOT).as_posix()
    blob = (
        subprocess.check_output(
            ["git", "hash-object", "-w", "--path", relative, "--stdin"],
            input=path.read_bytes(),
            cwd=ROOT,
        )
        .decode()
        .strip()
    )
    filtered = subprocess.check_output(["git", "cat-file", "blob", blob], cwd=ROOT)
    return {"git_blob": blob, "git_blob_sha256": digest(filtered)}


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--dpapi-resource-reference", type=Path, required=True)
    parser.add_argument("--powershell", type=Path, required=True)
    arguments = parser.parse_args()
    if os.name != "nt":
        parser.error("this evidence seal's DPAPI opt-in requires Windows")
    if (RUN / "artifact_manifest.json").exists():
        raise RuntimeError("material already sealed")
    reference = str(arguments.dpapi_resource_reference.resolve())
    if "'" in reference:
        raise ValueError("resource reference contains an unsupported quote")
    result = subprocess.run(
        [
            str(arguments.powershell),
            "-NoProfile",
            "-Command",
            "$r18Protected=Get-Content -LiteralPath '" + reference + "' -Raw; "
            "$r18Clear=$r18Protected | ConvertTo-SecureString | "
            "ConvertFrom-SecureString -AsPlainText; [Console]::Write($r18Clear)",
        ],
        capture_output=True,
        check=True,
        timeout=15,
    )
    original = make_url(json.loads(result.stdout)["TEST_DATABASE_URL"])
    assert original.host == "127.0.0.1" and original.port == 25432 and original.password
    secret_values = [
        SecretStr(original.render_as_string(hide_password=False)),
        SecretStr(original.set(database="postgres").render_as_string(hide_password=False)),
        SecretStr(original.password),
    ]
    for path in RUN.glob("*.json"):
        database_name = json.loads(path.read_bytes()).get("owned_database")
        if database_name:
            assert database_name.startswith("test_dianzi_r18_expiry_fix2_")
            secret_values.append(
                SecretStr(
                    original.set(database=database_name).render_as_string(hide_password=False)
                )
            )
    source_paths = [ROOT / path for path in SOURCE_PATHS]
    material_paths = [ROOT / REPORT_PATH]
    material_paths.extend(
        sorted(
            path
            for path in RUN.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.name not in {"raw_artifacts.zip", "artifact_manifest.json"}
        )
    )
    scan = []
    for path in source_paths + material_paths:
        content = path.read_bytes()
        leaked = any(value.get_secret_value().encode() in content for value in secret_values)
        scan.append({"path": path.relative_to(ROOT).as_posix(), "exact_dsn_or_password": leaked})
    assert not any(entry["exact_dsn_or_password"] for entry in scan)
    scan_path = RUN / "final_secret_scan.json"
    scan_path.write_text(
        json.dumps(
            {
                "observed_at": datetime.now().astimezone().isoformat(),
                "scope": "only final fix source, report and owned run files",
                "credential_values_loaded_only_in_memory": True,
                "files": scan,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    material_paths.append(scan_path)
    all_paths = source_paths + material_paths
    archive_path = RUN / "raw_artifacts.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in all_paths:
            archive.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
    all_paths.append(archive_path)
    records = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "raw_sha256": digest(path.read_bytes()),
            "size_bytes": path.stat().st_size,
            **git_blob_record(path),
        }
        for path in all_paths
    ]
    source_tree = subprocess.check_output(
        ["git", "rev-parse", SOURCE_COMMIT + "^{tree}"], cwd=ROOT, text=True
    ).strip()
    for source_relative in SOURCE_PATHS:
        assert git_blob_record(ROOT / source_relative)["git_blob_sha256"] == digest(
            subprocess.check_output(
                ["git", "show", SOURCE_COMMIT + ":" + source_relative], cwd=ROOT
            )
        )
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "base_material_commit": "c0428cb9801549c3bc778060153899e4b72028a2",
        "source_commit": SOURCE_COMMIT,
        "source_tree": source_tree,
        "state": "awaiting_review",
        "scope": "R18 API-key post-lock expiry and quota time fix 2 only",
        "files": records,
        "hash_mode": "raw_sha256=original bytes; git_blob_sha256=actual Git text filters",
        "raw_archive": "raw_artifacts.zip keeps originals; old 88/100-record archives unchanged",
        "exclusions": [
            "artifact_manifest.json self-reference",
            "__pycache__ generated bytecode",
            "raw_artifacts.zip excluded from its own archive",
        ],
    }
    (RUN / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "sealed_records": len(records),
                "source_commit": SOURCE_COMMIT,
                "exact_dsn_or_password": False,
                "state": "awaiting_review",
            }
        )
    )


if __name__ == "__main__":
    main()
