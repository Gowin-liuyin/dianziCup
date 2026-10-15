"""离线核验旧冻结102件材料和原失败gzip，不修改原材料或打印巨行。"""

import gzip
import hashlib
import io
import json
import subprocess
from pathlib import Path

workspace = Path(__file__).resolve().parents[3]
baseline_sha = "e651a0576785de4d8f9bf4e0dd114c8984bfd2d3"
manifest_path = "reports/runs/recovery_r11_manifest_parser_20261016/evidence_manifest.json"
manifest_bytes = subprocess.check_output(
    ["git", "show", f"{baseline_sha}:{manifest_path}"], cwd=workspace
)
manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
if manifest_hash != "e1827675743d736036c0d6ded14ce3243280ef96dd694033a431253066d30a92":
    raise ValueError("original manifest body hash mismatch")
manifest = json.loads(manifest_bytes)
for artifact in manifest["artifacts"]:
    blob = subprocess.check_output(
        ["git", "show", f"{baseline_sha}:{artifact['path']}"], cwd=workspace
    )
    if (
        len(blob) != artifact["size_bytes"]
        or hashlib.sha256(blob).hexdigest() != artifact["sha256"]
    ):
        raise ValueError(f"original artifact mismatch: {artifact['path']}")
preserved_paths = [
    "reports/runs/recovery_r11_manifest_parser_20261016",
    "reports/tasks/R11-manifest-parser.md",
    "backend/tests/unit/test_r11_manifest_parser.py",
    "backend/tests/contract/test_r11_manifest_candidate.py",
    "backend/tests/security/test_r11_manifest_parser_boundary.py",
]
unchanged = subprocess.check_output(
    ["git", "diff", "--name-only", baseline_sha, "--", *preserved_paths], cwd=workspace
)
if unchanged:
    raise ValueError("original run, report or original tests were modified")
gzip_path = "reports/runs/recovery_r11_manifest_parser_20261016/green_boundary.stdout.log.gz"
compressed = subprocess.check_output(["git", "show", f"{baseline_sha}:{gzip_path}"], cwd=workspace)
if (
    hashlib.sha256(compressed).hexdigest()
    != "6a03747311af06c0812c21743004c3cc046ac1a2f62dd9b60f004e0ce759cad6"
):
    raise ValueError("original compressed failure hash mismatch")
raw_size = 0
raw_hash = hashlib.sha256()
with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
    while block := stream.read(65536):
        raw_size += len(block)
        raw_hash.update(block)
expected_raw_hash = "3cccbce776d43c2fb1910a851859ae70de0d3290a387efbd870814e78d8b0323"
if raw_size != 41951937 or raw_hash.hexdigest() != expected_raw_hash:
    raise ValueError("original failure decompressed bytes mismatch")
review_probe = Path(__file__).resolve().parent / "test_independent_manifest_review.py"
review_hash = hashlib.sha256(review_probe.read_bytes()).hexdigest()
if review_hash != "ac13a06334ea163e5c3f95da0d7592aaa7c61a232b1ed7178be6b99983ab2b1c":
    raise ValueError("independent 38 probe bytes were altered")
print(
    json.dumps(
        {
            "baseline_sha": baseline_sha,
            "original_manifest_body_sha256": manifest_hash,
            "original_artifacts_verified": len(manifest["artifacts"]),
            "original_run_report_and_65_test_sources_unchanged": True,
            "original_failure_gzip_sha256": hashlib.sha256(compressed).hexdigest(),
            "original_failure_decompressed_size": raw_size,
            "original_failure_decompressed_sha256": raw_hash.hexdigest(),
            "original_review_38_probe_sha256": review_hash,
        },
        indent=2,
    )
)
