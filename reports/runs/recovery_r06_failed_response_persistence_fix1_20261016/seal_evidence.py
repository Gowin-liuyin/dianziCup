"""Seal the regression fix and verify historical raw bytes without rewriting them."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ORIGINAL = ROOT / "reports/runs/recovery_r06_failed_response_persistence_20261016"
ORIGINAL_SHA = "9eb01d7ba843116122a9a2462f3b74a2626cc48c"
CODE_SHA = "e1bae9db650df7946417cf42ec3817484514483a"
REPORT = ROOT / "reports/tasks/R06-failed-response-persistence-fix1.md"
author_manifest = json.loads((ORIGINAL / "artifact_manifest.json").read_text(encoding="utf-8"))
historical = [ROOT / name for name in author_manifest["artifacts"]]
historical.append(ORIGINAL / "artifact_manifest.json")
mismatches = []
for path in historical:
    name = path.relative_to(ROOT).as_posix()
    blob = subprocess.check_output(["git", "show", f"{ORIGINAL_SHA}:{name}"], cwd=ROOT)
    if blob != path.read_bytes():
        mismatches.append(name)
assert not mismatches
checks = {
    "at": datetime.now().astimezone().isoformat(),
    "historical_sha": ORIGINAL_SHA,
    "historical_file_count": len(historical),
    "original_working_bytes_vs_git_blob_mismatches": mismatches,
    "code_sha": CODE_SHA,
}
(RUN / "historical_bytes_audit.json").write_text(
    json.dumps(checks, indent=2), encoding="utf-8", newline="\n"
)
counts = {}
for path in RUN.glob("*.xml"):
    suite = ET.parse(path).getroot().find("testsuite")
    counts[path.stem] = {
        key: suite.attrib[key] for key in ("tests", "errors", "failures", "skipped", "time")
    }
    counts[path.stem]["case_ids"] = [
        case.attrib.get("classname", "") + "." + case.attrib.get("name", "")
        for case in suite.findall("testcase")
    ]
(RUN / "test_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8", newline="\n")
configuration = json.loads(
    subprocess.check_output(
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        text=True,
        timeout=10,
    )
)
connection = configuration["TEST_DATABASE_URL"]
credentials = [connection, unquote(urlsplit(connection).password or "")]
paths = [path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json"]
paths.append(REPORT)
secret_matches = [
    path.relative_to(ROOT).as_posix()
    for path in paths
    if any(credential and credential.encode() in path.read_bytes() for credential in credentials)
]
assert not secret_matches
(RUN / "secret_scan.json").write_text(
    json.dumps(
        {
            "at": datetime.now().astimezone().isoformat(),
            "checked_files": len(paths),
            "provider_secrets_read": 0,
            "matches": secret_matches,
        },
        indent=2,
    ),
    encoding="utf-8",
    newline="\n",
)
paths = sorted(
    path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json"
)
paths.append(REPORT)
artifacts = {
    path.relative_to(ROOT).as_posix(): {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
    }
    for path in paths
}
manifest = RUN / "artifact_manifest.json"
manifest.write_text(
    json.dumps(
        {
            "frozen_at": datetime.now().astimezone().isoformat(),
            "code_sha": CODE_SHA,
            "original_material_sha": ORIGINAL_SHA,
            "artifacts": artifacts,
        },
        indent=2,
    ),
    encoding="utf-8",
    newline="\n",
)
print(
    json.dumps(
        {
            "artifacts": len(artifacts),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "historical_byte_matches": len(historical),
            "credential_matches": len(secret_matches),
        }
    )
)
