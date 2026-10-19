"""Seal finite owned evidence files while scanning known secret values in memory."""

from common import OBSERVER, OBSERVER_SHA, PRODUCT_SHA, RUN, now, verify_authorization, write

verify_authorization()

import hashlib
import json
import os

report = RUN.parents[1] / "tasks/R06-live-segment-8a.md"
secrets = tuple(value.encode() for value in json.loads(os.environ["DIANZI_LOG_SECRET_VALUES"]) if value)
excluded = {"artifact_manifest.json", "freeze.log", "freeze_command.json"}
files = [path for path in RUN.rglob("*") if path.is_file() and path.name not in excluded] + [report]
findings = []
manifest = {}
for path in files:
    contents = path.read_bytes()
    label = str(path.relative_to(RUN)) if path.is_relative_to(RUN) else str(path)
    if any(secret in contents for secret in secrets):
        findings.append(label)
    manifest[label] = {"bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
assert not findings
observer_files = {name: {"bytes": (OBSERVER / name).stat().st_size, "sha256": hashlib.sha256((OBSERVER / name).read_bytes()).hexdigest()} for name in ("observe.py", "observation_log.py", "pg_snapshot.py")}
write("artifact_manifest.json", {"frozen_at": now(), "product_sha": PRODUCT_SHA, "observer_sha": OBSERVER_SHA, "observer_files_original_blob_verified": observer_files, "secret_scan_files": len(files), "secret_findings": findings, "excluded_freeze_outputs": sorted(excluded), "files": manifest, "startup_pass": False, "six_hour_pass": False})
print(json.dumps({"frozen_files": len(files), "secret_findings": len(findings), "six_hour_pass": False}))
